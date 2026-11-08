using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

[System.Serializable]
public class DriveCmd
{
    public float fl, fr, rl, rr;
}

public class RoboManager : MonoBehaviour
{
    public PythonConnection pythonSide;
    public PiConnection piSide;
    public RawImage videoDisplay;

    public float deadzone = 0.15f;
    public float sendRate = 20f;   // messages per second

    private Texture2D tex;
    private InputAction leftStick, rightStick;
    private float timer;

    void Awake()
    {
        tex = new Texture2D(2, 2, TextureFormat.RGB24, false);
        videoDisplay.texture = tex;
        videoDisplay.gameObject.SetActive(true);

        leftStick  = new InputAction("LeftStick",  InputActionType.Value, "<XRController>{LeftHand}/thumbstick");
        rightStick = new InputAction("RightStick", InputActionType.Value, "<XRController>{RightHand}/thumbstick");
    }

    void OnEnable()
    {
        piSide.OnFrameReceived += ShowFrame;
        leftStick.Enable();
        rightStick.Enable();
    }

    void OnDisable()
    {
        piSide.OnFrameReceived -= ShowFrame;
        leftStick.Disable();
        rightStick.Disable();
        piSide.SendDrive(JsonUtility.ToJson(new DriveCmd()));   // stop
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer < 1f / sendRate) return;
        timer = 0f;
        
        Vector2 l = Dead(leftStick.ReadValue<Vector2>());
        Vector2 r = Dead(rightStick.ReadValue<Vector2>());

        var cmd = new DriveCmd
        {
            fl = l.y + l.x,   // left stick left  -> front goes backward
            rl = l.y - l.x,   //                  -> rear goes forward
            fr = r.y - r.x,   // right stick left -> front goes forward
            rr = r.y + r.x    //                  -> rear goes backward
        };

        // keep everything within -1..1
        float max = Mathf.Max(1f, Mathf.Abs(cmd.fl), Mathf.Abs(cmd.fr),
                                Mathf.Abs(cmd.rl), Mathf.Abs(cmd.rr));
        cmd.fl /= max; cmd.fr /= max; cmd.rl /= max; cmd.rr /= max;

        piSide.SendDrive(JsonUtility.ToJson(cmd));
    }

    Vector2 Dead(Vector2 v) => v.magnitude < deadzone ? Vector2.zero : v;

    void ShowFrame(byte[] jpg) { tex.LoadImage(jpg); }

    void OnDestroy() { if (tex != null) Destroy(tex); }
}