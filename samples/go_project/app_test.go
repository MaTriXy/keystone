package app

import "testing"

func TestAdd(t *testing.T) {
	if Add(1, 2) != 3 {
		t.Error("expected 3")
	}
}

func TestMultiply(t *testing.T) {
	if Multiply(2, 3) != 6 {
		t.Error("expected 6")
	}
}
