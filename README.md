# 4SMART-C01 Sensor Utility

Windows desktop utility for the SemeaTech 4SMART-C01 electrochemical gas sensor module. It communicates with one module through a USB-UART adapter, displays live concentration, plots realtime history, records CSV data, shows raw TX/RX HEX traffic, and provides deliberate service commands for zero-setting, calibration, address change, and calibration gas concentration.

Protocol source: `4SMART-C01_EN V1.4.pdf`, Application Note AN230526, REV 1.4.

## Hardware

- SemeaTech 4SMART-C01 module
- Stable 3.3-5.5 VDC supply
- Compatible USB-UART adapter
- Windows 10 or Windows 11

Important wiring warning:

```text
4SMART-C01 UART is 3.0 V TTL.
Use a compatible USB-UART interface.
Do not connect it directly to a true +/-RS-232 interface.
```

Default serial settings from the manual:

- Baud: 9600 bps
- Data bits: 8
- Stop bits: 1
- Parity/check bit: none
- Default module address: `0x01`

## Safety

The manual states that the module:

- does not have intrinsic-safety certification
- does not have explosion-proof certification
- must not be used in hazardous locations as such
- does not have reverse-polarity protection
- does not have ESD protection
- should use a stable DC supply
- should use a supply with voltage fluctuation below 1%

This utility is a diagnostic/calibration tool. It does not provide certified gas monitoring or explosion safety.

## Install And Run

```bash
pip install -r requirements.txt
python main.py
```

To test without hardware, enable **Simulation Mode** before connecting. Simulation data is clearly marked in the UI and CSV logs.

## Basic Workflow

1. Wire VIN, GND, TX, and RX through a 3.0 V TTL-compatible USB-UART adapter.
2. Launch the utility.
3. Select the COM port.
4. Confirm address, usually `0x01`.
5. Click **Connect**.
6. Click **Read Information** if it was not read automatically.
7. Click **Start Acquisition**.
8. Optionally click **Start Logging** and choose a log directory.

## Dashboard

The dashboard shows:

- sensor type from the module information response
- current concentration with the module-reported unit
- measurement range
- calibration gas concentration
- high and low alarm points
- min, max, average, and sample count
- realtime pyqtgraph plot with selectable history window

Alarm lines are software display thresholds based on the points returned by module information. The utility does not implement or claim undocumented hardware alarm commands.

The Service tab also lets you override the software display Low/High alarm thresholds. These values are saved in application settings and affect the dashboard highlight and graph alarm lines only. The PDF does not define commands for writing hardware alarm points to the module, so the utility does not transmit undocumented alarm-setting frames.

## Service Commands

The Service tab implements only documented commands:

- `0x0F` Read module information
- `0x02` Zero-setting
- `0x03` Sensor calibration
- `0x04` Change module address
- `0x05` Change calibration gas concentration

Zero-setting and calibration always show confirmation dialogs. Realtime acquisition is suspended while a service transaction is active. The utility waits for the module's actual success/failure response and never assumes success from elapsed time alone.

After changing calibration gas concentration, the utility reads module information again and verifies the reported concentration.

The Service tab includes address scanning. It sends `Read Module Information` sequentially over the selected address range and lists devices that return valid CRC-checked responses. After selecting a found device, click **Use Selected Address** to make it the active address and read module information again.

## Serial Monitor

The Serial Monitor tab shows timestamped TX/RX HEX frames and marks:

- valid RX
- CRC errors
- malformed frames
- garbage bytes
- timeouts

Raw HEX send is available for developer diagnostics. It sends exactly the bytes entered, bypasses normal command validation, and listens briefly for a response so TX/RX traffic appears in the monitor.

## CSV Logging

CSV columns:

```csv
timestamp,sensor_type,address,value,unit,status,simulation
```

A companion `.metadata.json` file is created with module info, COM port, acquisition interval, and simulation flag.

## Tests

```bash
python -m pytest
```

Tests cover CRC examples from the PDF, command-frame generation, module information decoding, concentration decoding, CRC failure, wrong address, truncation, and stream parser recovery.

## Build Standalone EXE

```bat
build.bat
```

The executable will be created under:

```text
dist\4SMART-C01-Sensor-Utility\4SMART-C01-Sensor-Utility.exe
```

## Protocol Notes

See `docs/protocol_notes.md` for PDF formatting issues and implementation choices.
