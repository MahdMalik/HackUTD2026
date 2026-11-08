using UnityEngine;
using UnityEngine.InputSystem;

public class InputTest : MonoBehaviour
{
    void Update()
    {
        if (Mouse.current != null)
        {
            if (Mouse.current.leftButton.wasPressedThisFrame)
                Debug.Log("Mouse clicked!");

            if (Mouse.current.position.ReadValue() != Vector2.zero)
                Debug.Log("Mouse detected at: " +
                    Mouse.current.position.ReadValue());
        }
    }
}