# 05 — Fase 1: Hardware e Firmware

> Riferimento: Roadmap Fase 1

---

## Obiettivo

Heltec V3 operativo con firmware WiFi MeshCore, IP fisso, porta TCP 5000 raggiungibile dal RPi.

## Prerequisiti

- Heltec WiFi LoRa 32 V3
- Cavo USB-C per flash
- Accesso alla rete WiFi locale
- PC con Python 3 e `esptool` installato
- Raspberry Pi connesso alla stessa rete WiFi

## F1.1 — Compilazione Firmware WiFi

Il firmware WiFi **non e' disponibile precompilato**: SSID e password vengono incorporati a compile-time.

### Opzione A — Script automatico (consigliata)

```bash
git clone https://github.com/ilikehamradio/meshcore_heltecv3_wifi
cd meshcore_heltecv3_wifi
./build.sh
# Richiede: regione LoRa -> 868 MHz EU (opzione 4)
#           SSID e password WiFi
# Output:   firmware-merged.bin
```

### Opzione B — Compilazione manuale con PlatformIO

```bash
git clone https://github.com/meshcore-dev/MeshCore
cd MeshCore
# Editare variants/heltec_v3/platformio.ini:
#   -D WIFI_SSID="NomeTuaRete"
#   -D WIFI_PWD="TuaPassword"
pio run -e Heltec_v3_companion_radio_wifi
```

> **SICUREZZA**: Non condividere mai il binario compilato — contiene SSID e password in chiaro.

## F1.2 — Flash dell'Heltec V3

```bash
# Modalita' bootloader: tieni BOOT, collega USB, rilascia BOOT
esptool.py --chip esp32s3 --baud 921600 \
           write_flash 0x0 firmware-merged.bin
```

**Nota**: l'Heltec V3 usa ESP32-**S3**, non ESP32 generico. Usare `--chip esp32s3`.

## F1.3 — Configurazione Rete

1. **Trovare il MAC address** dell'Heltec V3:
   - Dal display OLED (se il firmware lo mostra)
   - Dal pannello admin del router WiFi
   - Dalla porta seriale: `esptool.py --chip esp32s3 read_mac`

2. **Creare DHCP reservation** sul router:
   - Assegnare IP fisso, es. `192.168.1.50`
   - Questo e' essenziale: il BBS deve sapere dove trovare il companion

3. **Verificare raggiungibilita' dal RPi**:

```bash
# Dal Raspberry Pi
ping -c 3 192.168.1.50
nc -zv 192.168.1.50 5000   # deve rispondere "Connection succeeded"
```

## F1.4 — Verifica Display OLED

Dopo il flash, il display OLED dell'Heltec dovrebbe mostrare:
- Nome del nodo
- Frequenza radio (868 MHz)
- Stato WiFi (connesso/IP)
- Eventuale conteggio messaggi

Se il display resta spento, verificare:
- Alimentazione USB stabile
- Firmware compilato per la variante corretta (V3, non V2)

## Troubleshooting

| Problema | Causa probabile | Soluzione |
|----------|----------------|-----------|
| `esptool` non trova il dispositivo | Bootloader non attivato | Tieni BOOT, collega USB, rilascia BOOT |
| WiFi non si connette | SSID/password errati nel firmware | Ricompilare con credenziali corrette |
| Porta 5000 non risponde | Firmware non WiFi | Verificare di aver compilato la variante `companion_radio_wifi` |
| IP cambia dopo riavvio | Nessuna DHCP reservation | Configurare IP statico sul router |
| Display spento | Firmware per variante sbagliata | Verificare chip target (V3 = ESP32-S3) |

## Criteri di Completamento

- [ ] Heltec V3 appare in rete con IP fisso `192.168.1.50`
- [ ] Porta TCP 5000 raggiungibile (`nc` risponde)
- [ ] Display OLED mostra nome nodo e stato radio
- [ ] Firmware non modificato rispetto al sorgente ufficiale
- [ ] Ping dal RPi all'Heltec con latenza < 10ms
