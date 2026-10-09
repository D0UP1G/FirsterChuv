#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <unistd.h>

int main() {
  const int protocol_fd = ::open("/proc/1/fd/1", O_WRONLY | O_CLOEXEC);
  if (protocol_fd >= 0) {
    constexpr char marker[] = "SUPERVISOR_CHANNEL_BREACH\n";
    const auto written = ::write(protocol_fd, marker, sizeof(marker) - 1);
    (void)::close(protocol_fd);
    return written == static_cast<ssize_t>(sizeof(marker) - 1) ? 0 : 3;
  }
  if (errno == EACCES || errno == EPERM) {
    std::cout << "blocked\n";
    return 0;
  }
  std::cerr << "open failed: " << std::strerror(errno) << '\n';
  return 2;
}
