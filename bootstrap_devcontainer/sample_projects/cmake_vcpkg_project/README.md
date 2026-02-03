# CMake + vcpkg Sample Project

A minimal C++ project using CMake and vcpkg to demonstrate dependency caching in devcontainers.

## Dependencies

- **fmt**: A modern formatting library (installed via vcpkg)

## Building

```bash
# Install vcpkg if not already installed
git clone https://github.com/microsoft/vcpkg.git
./vcpkg/bootstrap-vcpkg.sh

# Configure and build
cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE=./vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build build

# Run tests
ctest --test-dir build --output-on-failure
```

## Project Structure

```
├── CMakeLists.txt      # Build configuration
├── vcpkg.json          # vcpkg manifest (dependencies)
├── src/
│   ├── greeter.hpp     # Library header
│   ├── greeter.cpp     # Library implementation
│   └── main.cpp        # Main executable
└── tests/
    └── test_greeter.cpp  # Unit tests
```
