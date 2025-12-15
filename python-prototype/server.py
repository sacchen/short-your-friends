import asyncio


async def handle_client(reader, writer):
    """
    This functions runs once from every connection.
    10 concurrent versions if 10 people connect.
    """

    # Get IP address of the person connecting
    addr = writer.get_extra_info("peername")
    print(f"[+] New connection from {addr}")

    try:
        while True:
            # Wait for data
            # Looking for \n. Using Newline Delimited JSON
            data = await reader.readuntil(b"\n")

            # Decode bytes -> string
            message = data.decode().strip()
            print(f"Received: {message}")

            # Echo: Send it back
            response = f"Echo: {message}\n"
            writer.write(response.encode())
            await writer.drain()  # Makes sure buffer flushes to network

    except asyncio.IncompleteReadError:
        print(f"[-] Client {addr} disconnected.")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    # Start server on localhost port 8888
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[*] Serving on {addrs}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        # Run event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
