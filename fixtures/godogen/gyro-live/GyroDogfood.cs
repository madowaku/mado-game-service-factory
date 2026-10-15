using Godot;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

// Hand-authored engine verification fixture, intentionally NOT Godogen output.
// Injects deterministic Godot Input actions into actual _PhysicsProcess code.
// Video frames and JSON state samples come from the same game process.
public partial class GyroDogfood : Node2D
{
    private readonly List<object> _samples = new();
    private int _tick;
    private float _playerX = 320.0f;
    private readonly float _playerY = 180.0f;
    private string _tracePath = "";
    private string _runId = "";
    private string _missionId = "";

    private static string Argument(string[] args, string key)
    {
        for (int i = 0; i + 1 < args.Length; i++)
        {
            if (args[i] == key)
                return args[i + 1];
        }
        return "";
    }

    public override void _Ready()
    {
        string[] args = Godot.OS.GetCmdlineUserArgs();
        _tracePath = Argument(args, "--mgsf-trace");
        _runId = Argument(args, "--mgsf-run-id");
        _missionId = Argument(args, "--mgsf-mission-id");
        if (string.IsNullOrWhiteSpace(_tracePath) ||
            string.IsNullOrWhiteSpace(_runId) ||
            string.IsNullOrWhiteSpace(_missionId))
        {
            GD.PushError("GYRO dogfood requires trace, run id and mission id");
            GetTree().Quit(2);
            return;
        }

        InputMap.AddAction("tilt_left");
        InputMap.AddAction("tilt_right");
        QueueRedraw();
    }

    public override void _PhysicsProcess(double delta)
    {
        _tick++;
        // Deterministic injected input, not a human controller or agent claim.
        Input.ActionRelease("tilt_right");
        Input.ActionRelease("tilt_left");
        string action = "idle";
        if (_tick >= 30 && _tick <= 120)
        {
            Input.ActionPress("tilt_right");
            action = "right";
        }
        else if (_tick >= 180 && _tick <= 270)
        {
            Input.ActionPress("tilt_left");
            action = "left";
        }
        float axis = Input.GetAxis("tilt_left", "tilt_right");
        _playerX = Mathf.Clamp(_playerX + axis * 2.0f, 30, 610);
        if (_tick == 1 || _tick % 15 == 0)
        {
            _samples.Add(new {
                tick = _tick,
                input = action,
                state = new { x = _playerX, y = _playerY }
            });
        }
        // Save before process exit too: --quit-after is controlled by the movie writer.
        if (_tick == 420)
            PersistTrace();
        QueueRedraw();
    }

    private void PersistTrace()
    {
        if (string.IsNullOrWhiteSpace(_tracePath))
            return;
        var payload = new {
            schema_version = 1,
            engine = "godot",
            mission_id = _missionId,
            run_id = _runId,
            input_provenance = "godot_input_action_scripted",
            samples = _samples,
        };
        Directory.CreateDirectory(Path.GetDirectoryName(_tracePath)!);
        File.WriteAllText(_tracePath, JsonSerializer.Serialize(payload));
        GD.Print($"MGSF_GYRO_STATE_TRACE_OK samples={_samples.Count} ticks={_tick}");
    }

    public override void _Draw()
    {
        DrawRect(new Rect2(0, 0, 640, 360), new Color(0.055f, 0.072f, 0.125f), true);
        DrawRect(new Rect2(26, 146, 588, 68), new Color(0.16f, 0.19f, 0.3f), true);
        DrawLine(new Vector2(320, 140), new Vector2(320, 220),
                 new Color(0.45f, 0.52f, 0.6f), 2.0f);
        DrawCircle(new Vector2(_playerX, _playerY), 22.0f, new Color(0.15f, 0.83f, 0.73f));
        DrawCircle(new Vector2(_playerX - 6, _playerY - 7), 6.0f,
                   new Color(0.77f, 1.0f, 0.95f));
    }

    public override void _ExitTree()
    {
        Input.ActionRelease("tilt_right");
        Input.ActionRelease("tilt_left");
        PersistTrace();
    }
}
