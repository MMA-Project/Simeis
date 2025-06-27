BINARY_NAME = simeis-server
TARGET = target/release/$(BINARY_NAME)
MANUAL_FILE = doc/manual.typ
MANUAL_OUTPUT = doc/manual.pdf

release:
	RUSTFLAGS="-C codegen-units=1 -C code-model=large" cargo build --release
	strip $(TARGET)

check:
	cargo check

test:
	cargo test

clean:
	cargo clean

manual:
	typst compile $(MANUAL_FILE) $(MANUAL_OUTPUT)