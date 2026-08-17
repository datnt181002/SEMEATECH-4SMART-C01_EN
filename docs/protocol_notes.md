# 4SMART-C01 Protocol Notes

Protocol source: `4SMART-C01_EN V1.4.pdf`, SemeaTech 4SMART-C01 Sensor Module, Application Note AN230526, REV 1.4.

CRC16 is implemented from Appendix 1: initial value `0xFFFF`, polynomial `0xA001`, calculated over command/data bytes only, excluding `0xAA`, CRC bytes, and `0xEE`. The transmitted order matches the PDF examples, e.g. `05 01 01 F4 -> 51 3F`.

| PDF location | Documented value | Implemented interpretation | Reason |
|---|---|---|---|
| Page 2, Communication Settings | Check bit: `None` | Serial parity is `PARITY_NONE` | The table states no check bit. CRC is a protocol field, not UART parity. |
| Page 5, Address Modification request | `AA 04 02 C82 B1 EE` | `AA 04 02 82 B1 EE` | `C82` is a formatting typo. CRC over `04 02` is `82 B1`, consistent with the command note. |
| Page 4/5, response CRC notes | Some notes read `Byte 2 aByte 3 and Byte 4` | CRC covers response body bytes before CRC, such as `02 01 10` or `05 01 10 01 F4` | The PDF text is corrupted, but examples verify cleanly using the Appendix 1 algorithm over command/address/status/data. |
| Page 3, concentration wording | Byte2 says "Information reading command" for command `0x01` | Treated as gas concentration request/response | Section title and response fields define it as concentration reading. |
| Page 3, concentration unit text | Data says `(ppm)` | GUI uses module-reported unit | Page 2 defines unit codes. The utility does not hardcode ppm. |
| Page 4, zero/calibration timing | LED flashes 30 seconds for zero, 120 seconds for calibration | UI waits for actual module response and does not infer success from timers | The protocol success/failure response is authoritative. |

