#include <iostream>
#include <string>

int main() {
  std::cout.setf(std::ios::unitbuf);
  const std::string block(4096, 'x');
  for (;;) std::cout << block;
}
