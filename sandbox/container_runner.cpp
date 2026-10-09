#include <algorithm>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <sys/resource.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <vector>

namespace {

constexpr std::size_t kMaxSourceBytes = 32 * 1024;
constexpr std::size_t kMaxArtifactBytes = 8 * 1024 * 1024;
constexpr std::size_t kMaxInputBytes = 64 * 1024;
constexpr std::size_t kMaxOutputBytes = 32 * 1024;
constexpr std::size_t kMaxDiagnosticsBytes = 8 * 1024;
constexpr auto kCompileTimeout = std::chrono::seconds(15);
constexpr auto kRunTimeout = std::chrono::seconds(2);

struct ChildResult {
  bool timed_out = false;
  int wait_status = 0;
};

std::string base64_encode(std::string_view input) {
  static constexpr char alphabet[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string encoded;
  encoded.reserve(((input.size() + 2) / 3) * 4);
  for (std::size_t i = 0; i < input.size(); i += 3) {
    const auto remaining = input.size() - i;
    const auto a = static_cast<unsigned char>(input[i]);
    const auto b = remaining > 1 ? static_cast<unsigned char>(input[i + 1]) : 0;
    const auto c = remaining > 2 ? static_cast<unsigned char>(input[i + 2]) : 0;
    encoded.push_back(alphabet[a >> 2]);
    encoded.push_back(alphabet[((a & 0x03) << 4) | (b >> 4)]);
    encoded.push_back(remaining > 1 ? alphabet[((b & 0x0f) << 2) | (c >> 6)] : '=');
    encoded.push_back(remaining > 2 ? alphabet[c & 0x3f] : '=');
  }
  return encoded;
}

bool write_all(int fd, std::string_view bytes) {
  std::size_t offset = 0;
  while (offset < bytes.size()) {
    const auto written = ::write(fd, bytes.data() + offset, bytes.size() - offset);
    if (written < 0 && errno == EINTR) continue;
    if (written <= 0) return false;
    offset += static_cast<std::size_t>(written);
  }
  return true;
}

bool write_file(const char* path, std::string_view bytes) {
  const int fd = ::open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0) return false;
  const bool okay = write_all(fd, bytes);
  const int close_result = ::close(fd);
  return okay && close_result == 0;
}

bool read_file_bounded(const char* path, std::size_t limit, std::string& contents,
                       bool& exceeded) {
  const int fd = ::open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) return false;
  struct stat info {};
  if (::fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < 0) {
    ::close(fd);
    return false;
  }
  const auto size = static_cast<std::size_t>(info.st_size);
  exceeded = size > limit;
  contents.clear();
  contents.resize(std::min(size, limit));
  std::size_t offset = 0;
  while (offset < contents.size()) {
    const auto count = ::read(fd, contents.data() + offset, contents.size() - offset);
    if (count < 0 && errno == EINTR) continue;
    if (count <= 0) {
      ::close(fd);
      return false;
    }
    offset += static_cast<std::size_t>(count);
  }
  return ::close(fd) == 0;
}

bool parse_size(std::string_view text, std::size_t& value) {
  if (text.empty() || text.size() > 10) return false;
  std::size_t parsed = 0;
  const auto result = std::from_chars(text.data(), text.data() + text.size(), parsed);
  if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) return false;
  value = parsed;
  return true;
}

bool read_request(std::string& first, std::string& input, std::size_t max_first_bytes) {
  std::string header;
  if (!std::getline(std::cin, header) || header.size() > 32) return false;
  std::istringstream fields(header);
  std::string first_size_text;
  std::string input_size_text;
  std::string extra;
  if (!(fields >> first_size_text >> input_size_text) || (fields >> extra)) return false;

  std::size_t first_size = 0;
  std::size_t input_size = 0;
  if (!parse_size(first_size_text, first_size) ||
      !parse_size(input_size_text, input_size) || first_size == 0 ||
      first_size > max_first_bytes || input_size > kMaxInputBytes) {
    return false;
  }

  first.resize(first_size);
  input.resize(input_size);
  std::cin.read(first.data(), static_cast<std::streamsize>(first_size));
  if (std::cin.gcount() != static_cast<std::streamsize>(first_size)) return false;
  if (input_size > 0) {
    std::cin.read(input.data(), static_cast<std::streamsize>(input_size));
    if (std::cin.gcount() != static_cast<std::streamsize>(input_size)) return false;
  }
  return true;
}

void emit_result(std::string_view status, std::optional<int> exit_code,
                 std::optional<int> signal, std::string_view stdout_bytes,
                 std::string_view stderr_bytes, std::string_view artifact = "") {
  std::cout << "{\"status\":\"" << status << "\",\"exitCode\":";
  if (exit_code.has_value()) std::cout << *exit_code;
  else std::cout << "null";
  std::cout << ",\"signal\":";
  if (signal.has_value()) std::cout << *signal;
  else std::cout << "null";
  std::cout << ",\"stdoutBase64\":\"" << base64_encode(stdout_bytes)
            << "\",\"stderrBase64\":\"" << base64_encode(stderr_bytes)
            << "\",\"artifactBase64\":\"" << base64_encode(artifact) << "\"}\n";
}

void emit_infrastructure_error() {
  emit_result("INFRASTRUCTURE_ERROR", std::nullopt, std::nullopt, "", "");
}

void set_child_limits(bool limit_output) {
  struct rlimit core_limit {0, 0};
  if (::setrlimit(RLIMIT_CORE, &core_limit) != 0) _exit(126);
  struct rlimit fd_limit {64, 64};
  if (::setrlimit(RLIMIT_NOFILE, &fd_limit) != 0) _exit(126);
  if (limit_output) {
    struct rlimit file_limit {kMaxOutputBytes, kMaxOutputBytes};
    if (::setrlimit(RLIMIT_FSIZE, &file_limit) != 0) _exit(126);
  }
}

void child_exec(const std::vector<std::string>& arguments, const char* input_path,
                const char* stdout_path, const char* stderr_path,
                bool limit_output) {
  if (::setpgid(0, 0) != 0 || ::chdir("/work") != 0) _exit(126);
  const int input_fd = ::open(input_path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  const int stdout_fd = ::open(stdout_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
  const int stderr_fd = ::open(stderr_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (input_fd < 0 || stdout_fd < 0 || stderr_fd < 0) _exit(126);
  if (::dup2(input_fd, STDIN_FILENO) < 0 || ::dup2(stdout_fd, STDOUT_FILENO) < 0 ||
      ::dup2(stderr_fd, STDERR_FILENO) < 0) {
    _exit(126);
  }
  ::close(input_fd);
  ::close(stdout_fd);
  ::close(stderr_fd);

  set_child_limits(limit_output);
  if (::clearenv() != 0 || ::setenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", 1) != 0 ||
      ::setenv("TMPDIR", "/work/tmp", 1) != 0 || ::setenv("HOME", "/work", 1) != 0 ||
      ::setenv("LC_ALL", "C", 1) != 0) {
    _exit(126);
  }

  std::vector<char*> argv;
  argv.reserve(arguments.size() + 1);
  for (const auto& argument : arguments) argv.push_back(const_cast<char*>(argument.c_str()));
  argv.push_back(nullptr);
  ::execvp(argv[0], argv.data());
  _exit(errno == ENOENT ? 127 : 126);
}

bool run_child(const std::vector<std::string>& arguments, const char* input_path,
               const char* stdout_path, const char* stderr_path,
               std::chrono::seconds timeout, bool limit_output, ChildResult& result) {
  const pid_t child = ::fork();
  if (child < 0) return false;
  if (child == 0) child_exec(arguments, input_path, stdout_path, stderr_path, limit_output);
  (void)::setpgid(child, child);

  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (true) {
    int status = 0;
    const pid_t waited = ::waitpid(child, &status, WNOHANG);
    if (waited == child) {
      result.wait_status = status;
      (void)::kill(-child, SIGKILL);  // Reap any background descendants of the solution.
      return true;
    }
    if (waited < 0 && errno != EINTR) return false;
    if (std::chrono::steady_clock::now() >= deadline) {
      result.timed_out = true;
      (void)::kill(-child, SIGKILL);
      while (::waitpid(child, &result.wait_status, 0) < 0) {
        if (errno == EINTR) continue;
        return false;
      }
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
}

bool make_directory(const char* path) {
  if (::mkdir(path, 0700) == 0 || errno == EEXIST) {
    struct stat info {};
    return ::lstat(path, &info) == 0 && S_ISDIR(info.st_mode);
  }
  return false;
}

}  // namespace

void compile_source(const std::string& source) {
  if (!write_file("/work/main.cpp", source) ||
      !write_file("/work/compiler.stdout", "") || !write_file("/work/compiler.stderr", "")) {
    emit_infrastructure_error();
    return;
  }
  ChildResult compile_result;
  const std::vector<std::string> compiler = {
      "g++", "-std=c++20", "-O2", "-pipe", "-fno-diagnostics-color", "-fmax-errors=20",
      "/work/main.cpp", "-o", "/work/program"};
  if (!run_child(compiler, "/dev/null", "/work/compiler.stdout", "/work/compiler.stderr",
                 kCompileTimeout, false, compile_result)) {
    emit_infrastructure_error();
    return;
  }
  if (compile_result.timed_out) {
    std::string diagnostics;
    bool ignored = false;
    (void)read_file_bounded("/work/compiler.stderr", kMaxDiagnosticsBytes, diagnostics, ignored);
    emit_result("COMPILE_TIMEOUT", std::nullopt, std::nullopt, "", diagnostics);
    return;
  }
  if (WIFSIGNALED(compile_result.wait_status)) {
    const int signal = WTERMSIG(compile_result.wait_status);
    if (signal == SIGKILL || signal == SIGXCPU) {
      emit_infrastructure_error();  // Do not infer a verdict from an unexplained kill.
      return;
    }
  }
  if (!WIFEXITED(compile_result.wait_status)) {
    emit_infrastructure_error();
    return;
  }
  const int compile_code = WEXITSTATUS(compile_result.wait_status);
  if (compile_code == 126 || compile_code == 127) {
    emit_infrastructure_error();
    return;
  }
  if (compile_code != 0) {
    std::string diagnostics;
    bool ignored = false;
    if (!read_file_bounded("/work/compiler.stderr", kMaxDiagnosticsBytes, diagnostics, ignored)) {
      emit_infrastructure_error();
      return;
    }
    emit_result("COMPILE_ERROR", compile_code, std::nullopt, "", diagnostics);
    return;
  }

  std::string artifact;
  bool artifact_exceeded = false;
  if (!read_file_bounded("/work/program", kMaxArtifactBytes, artifact, artifact_exceeded)) {
    emit_infrastructure_error();
    return;
  }
  if (artifact_exceeded) {
    emit_result("COMPILE_ARTIFACT_LIMIT", std::nullopt, std::nullopt, "", "");
    return;
  }
  if (artifact.empty()) {
    emit_infrastructure_error();
    return;
  }
  emit_result("COMPILED", 0, std::nullopt, "", "", artifact);
}

void run_program(const std::string& artifact, const std::string& input) {
  if (!write_file("/work/program", artifact) || ::chmod("/work/program", 0500) != 0 ||
      !write_file("/work/input", input) || !write_file("/work/program.stdout", "") ||
      !write_file("/work/program.stderr", "")) {
    emit_infrastructure_error();
    return;
  }
  ChildResult run_result;
  const std::vector<std::string> program = {"/work/program"};
  if (!run_child(program, "/work/input", "/work/program.stdout", "/work/program.stderr",
                 kRunTimeout, true, run_result)) {
    emit_infrastructure_error();
    return;
  }
  std::string stdout_bytes;
  std::string stderr_bytes;
  bool stdout_exceeded = false;
  bool stderr_exceeded = false;
  if (!read_file_bounded("/work/program.stdout", kMaxOutputBytes, stdout_bytes, stdout_exceeded) ||
      !read_file_bounded("/work/program.stderr", kMaxOutputBytes, stderr_bytes, stderr_exceeded)) {
    emit_infrastructure_error();
    return;
  }
  if (run_result.timed_out) {
    emit_result("TIME_LIMIT", std::nullopt, std::nullopt, stdout_bytes, stderr_bytes);
    return;
  }
  if (stdout_exceeded || stderr_exceeded ||
      (WIFSIGNALED(run_result.wait_status) && WTERMSIG(run_result.wait_status) == SIGXFSZ)) {
    emit_result("OUTPUT_LIMIT", std::nullopt, std::nullopt, stdout_bytes, stderr_bytes);
    return;
  }
  if (WIFSIGNALED(run_result.wait_status)) {
    const int signal = WTERMSIG(run_result.wait_status);
    if (signal == SIGKILL) {
      emit_result("KILLED_UNKNOWN", std::nullopt, signal, stdout_bytes, stderr_bytes);
    } else {
      emit_result("RUNTIME_ERROR", std::nullopt, signal, stdout_bytes, stderr_bytes);
    }
    return;
  }
  if (!WIFEXITED(run_result.wait_status)) {
    emit_infrastructure_error();
    return;
  }
  const int run_code = WEXITSTATUS(run_result.wait_status);
  emit_result(run_code == 0 ? "EXITED" : "RUNTIME_ERROR", run_code, std::nullopt,
              stdout_bytes, stderr_bytes);
}

int main(int argc, char* argv[]) {
  // Same-UID solution processes must not inspect /proc/1/fd and write into this protocol stream.
  if (::prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0) {
    emit_infrastructure_error();
    return 0;
  }
  if (argc != 2 || (std::string_view(argv[1]) != "compile" &&
                    std::string_view(argv[1]) != "run") ||
      !make_directory("/work/tmp")) {
    emit_infrastructure_error();
    return 0;
  }
  const std::string_view mode(argv[1]);
  std::string first;
  std::string input;
  const auto max_first_bytes = mode == "compile" ? kMaxSourceBytes : kMaxArtifactBytes;
  if (!read_request(first, input, max_first_bytes) ||
      (mode == "compile" && !input.empty())) {
    emit_infrastructure_error();
    return 0;
  }
  if (mode == "compile") compile_source(first);
  else run_program(first, input);
  return 0;
}
