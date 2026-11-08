using UnityEngine;
using UnityEngine.UI;

public class RoboManager : MonoBehaviour
{
    public PythonConnection pythonSide;
    public PiConnection piSide;
    public RawImage videoDisplay;

    private Texture2D tex;

    void Awake()
    {
        tex = new Texture2D(2, 2, TextureFormat.RGB24, false);
        videoDisplay.texture = tex;
    }

    void OnEnable()
    {
        videoDisplay.enabled = true;
        piSide.OnFrameReceived += ShowFrame;
    }

    void OnDisable()
    {
        piSide.OnFrameReceived -= ShowFrame;
    }

    void OnDestroy()
    {
        if (tex != null)
            Destroy(tex);
    }

    void ShowFrame(byte[] jpg)
    {
        tex.LoadImage(jpg);
    }
}