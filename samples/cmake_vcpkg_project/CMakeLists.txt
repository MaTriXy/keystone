cmake_minimum_required(VERSION 3.14)
project(hello_vcpkg VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find vcpkg-installed packages
find_package(fmt CONFIG REQUIRED)

# Main library
add_library(greeter src/greeter.cpp)
target_include_directories(greeter PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(greeter PRIVATE fmt::fmt)

# Main executable
add_executable(hello_world src/main.cpp)
target_link_libraries(hello_world PRIVATE greeter fmt::fmt)

# Tests
enable_testing()
add_executable(test_greeter tests/test_greeter.cpp)
target_link_libraries(test_greeter PRIVATE greeter fmt::fmt)
add_test(NAME test_greeter COMMAND test_greeter)
