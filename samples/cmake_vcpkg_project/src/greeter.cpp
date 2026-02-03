#include "greeter.hpp"
#include <fmt/format.h>

std::string greet(const std::string& name) {
    return fmt::format("Hello, {}!", name);
}
