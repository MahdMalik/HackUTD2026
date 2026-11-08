
using UnityEngine;
using NativeWebSocket;
using System;
using System.Threading.Tasks;

public class PythonConnection : MonoBehaviour
{
    public string pythonURL = "ws://10.222.215.168:6768";

    public UIScript uiScript;

    private WebSocket pythonSocket;

    private void Update()
    {
        pythonSocket?.DispatchMessageQueue();
    }

    public async void ConnectPython()
    {
        if (pythonSocket != null &&
            pythonSocket.State == WebSocketState.Open)
            return;

        try
        {
            Debug.Log("Connecting to Python...");

            pythonSocket = new WebSocket(pythonURL);

            pythonSocket.OnOpen += () =>
            {
                Debug.Log("Python connected!");
                uiScript.OnPythonConnect();
            };

            pythonSocket.OnError += (error) =>
            {
                Debug.LogError("Python error: " + error);
                uiScript.OnPythonFailConnect();
            };

            pythonSocket.OnClose += (code) =>
            {
                Debug.Log("Python disconnected.");
                uiScript.OnPythonFailConnect();
            };

            pythonSocket.OnMessage += (bytes) =>
            {
                string message =
                    System.Text.Encoding.UTF8.GetString(bytes);

                Debug.Log("Python says: " + message);
            };

            await pythonSocket.Connect();
        }
        catch (Exception e)
        {
            Debug.LogError("Python connection failed: " + e.Message);
            uiScript.OnPythonFailConnect();
        }
    }

    public async void DisconnectPython()
    {
        if (pythonSocket != null)
        {
            await pythonSocket.Close();
            pythonSocket = null;
        }
    }

    public async Task SendMessageToPython(string message)
    {
        if (pythonSocket != null &&
            pythonSocket.State == WebSocketState.Open)
        {
            await pythonSocket.SendText(message);
        }
        else
        {
            Debug.LogWarning("Python is not connected!");
        }
    }

    private async void OnDestroy()
    {
        if (pythonSocket != null)
            await pythonSocket.Close();
    }
}
