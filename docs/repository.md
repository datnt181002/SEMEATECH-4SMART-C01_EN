# Repository Layout

```text
.
├── app/                         # Application source code
│   ├── communication/           # Serial worker and sensor controller
│   ├── logging/                 # CSV data logger
│   ├── protocol/                # CRC, frames, parser, command builders, decoders
│   ├── widgets/                 # PySide6 UI widgets
│   └── main_window.py
├── docs/                        # Project and protocol documentation
├── tests/                       # Protocol/unit tests
├── main.py                      # GUI entry point
├── requirements.txt             # Runtime/test dependency shortcut
├── pyproject.toml               # Python project metadata and test config
├── build.bat                    # PyInstaller build helper
└── 4SMART-C01-Sensor-Utility.exe # Packaged release executable kept by request
```

The executable is intentionally kept in the repository root for easy handoff. Build intermediates such as `build/`, `dist/`, `.spec`, caches, and logs are ignored.

