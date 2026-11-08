using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class UIScript : MonoBehaviour
{
    public Button connectPython;
    public Button connectPi;
    public Button disconnectPi;
    public Button startTest;
    public TextMeshProUGUI pythonResult;
    public TextMeshProUGUI piResult;

    public PythonConnection pythonConnection;
    public PiConnection piConnection;

    public RoboManager robotManager;

    bool pythonConnected = false;
    bool piConnected = false;

    public Image mainImg;

    
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        Debug.Log("UIScript initialized");
        disconnectPi.interactable = false;
        startTest.interactable = false;
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
        pythonConnected = true;
        if(pythonConnected && piConnected) startTest.interactable = true;
    }

    public void OnPythonFailConnect()
    {
        pythonResult.text = "Python Failed Connect!";
        pythonConnected = false;
        startTest.interactable = false;
    }

    public void OnPiConnect()
    {
        piResult.text = "Pi Connected!";
        piConnected = true;
        disconnectPi.interactable = true;
        if(pythonConnected && piConnected) startTest.interactable = true;
    }

    public void OnPiFailConnect()
    {
        piResult.text = "Pi Failed Connect!";
        piConnected = false;
        startTest.interactable = false;
    }

    public void StartClicked()
    {
        mainImg.gameObject.SetActive(false);
        robotManager.gameObject.SetActive(true);
    }
}
