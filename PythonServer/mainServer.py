
import asyncio
import websockets


async def handle_connection(websocket):
    print("Unity connected!")

    try:
        async for message in websocket:
            print(f"Received from Unity: {message}")

            # Acknowledge that the message was received
            await websocket.send("Message received!")

    except websockets.exceptions.ConnectionClosed:
        print("Unity disconnected.")


async def main():
    server = await websockets.serve(
        handle_connection,
        "0.0.0.0",
        6768
    )

    print("Python WebSocket server running on port 6768")
    print("Waiting for Unity to connect...")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
