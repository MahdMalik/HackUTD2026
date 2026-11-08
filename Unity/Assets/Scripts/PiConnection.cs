
using UnityEngine;
using NativeWebSocket;
using System;

public class PiConnection : MonoBehaviour
{
    public string piURL = "ws://10.176.226.211:6767";

    public UIScript uiScript;

    private WebSocket piSocket;

    private void Update()
    {
        piSocket?.DispatchMessageQueue();
    }

    public async void ConnectPi()
    {
        if (piSocket != null &&
            piSocket.State == WebSocketState.Open)
            return;

        try
        {
            Debug.Log("Connecting to Raspberry Pi...");

            piSocket = new WebSocket(piURL);

            piSocket.OnOpen += () =>
            {
                Debug.Log("Raspberry Pi connected!");
                uiScript.OnPiConnect();
            };

            piSocket.OnError += (error) =>
            {
                Debug.LogError("Pi connection error: " + error);
                uiScript.OnPiFailConnect();
            };

            piSocket.OnClose += (code) =>
            {
                Debug.Log("Pi disconnected.");
                uiScript.OnPiFailConnect();
            };

            await piSocket.Connect();
        }
        catch (Exception e)
        {
            Debug.LogError("Pi connection failed: " + e.Message);
            uiScript.OnPiFailConnect();
        }
    }

    public async void DisconnectPi()
    {
        if (piSocket != null)
        {
            await piSocket.Close();
            piSocket = null;
        }
    }

    private async void OnDestroy()
    {
        if (piSocket != null)
            await piSocket.Close();
    }
}
