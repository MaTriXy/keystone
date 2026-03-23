#include "greeter.hpp"
#include <cassert>
#include <iostream>

int main() {
    // Test basic greeting
    assert(greet("World") == "Hello, World!");
    assert(greet("Alice") == "Hello, Alice!");
    assert(greet("") == "Hello, !");
    
    std::cout << "All tests passed!" << std::endl;
    return 0;
}
