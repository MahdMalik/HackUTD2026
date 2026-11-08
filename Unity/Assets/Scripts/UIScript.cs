using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class UIScript : MonoBehaviour
{
    public Button connectPython;
    public Button connectPi;
    public Button disconnectPi;
    public TextMeshProUGUI pythonResult;
    public TextMeshProUGUI piResult;

    public PythonConnection pythonConnection;
    public PiConnection piConnection;

    
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        Debug.Log("UIScript initialized");
    }
    // Update is called once per frame
    void Update()
    {
        
    }

    public void PythonButtonClicked()
    {
        Debug.Log("clicked.");
        connectPython.interactable = false;
        pythonConnection.ConnectPython();
    }

    public void PiButtonClicked()
    {
        connectPi.interactable = false;
        piConnection.ConnectPi();
    }

    public void CancelPiButtonClicked()
    {
        disconnectPi.interactable = false;
        connectPi.interactable = true;
        piResult.text = "";
        piConnection.DisconnectPi();
    }

    public void OnPythonConnect()
    {
        pythonResult.text = "Python Connected!";
    }

    public void OnPythonFailConnect()
    {
        pythonResult.text = "Python Failed Connect!";
    }

    public void OnPiConnect()
    {
        piResult.text = "Pi Connected!";
    }

    public void OnPiFailConnect()
    {
        piResult.text = "Pi Failed Connect!";
    }
}
