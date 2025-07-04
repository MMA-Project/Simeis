FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY target/release/simeis-server .

EXPOSE 8080

ENTRYPOINT ["./simeis-server"]