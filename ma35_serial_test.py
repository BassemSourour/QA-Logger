import serial

ser = serial.Serial(
    "COM18",
    baudrate=4800,
    bytesize=serial.SEVENBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=5
)

print("Listening on COM18. Press Print on the MA35...")

while True:
    data = ser.read(1)
    if data:
        print(data.hex(), data)