import struct

with open('bytecode.bin', 'rb') as f:
    d = f.read()
_, _, vc, sz = struct.unpack_from('<4sBBH', d, 0)
cd = d[8 : 8 + sz]
h = open('firmware_data.h', 'w')
h.write('#ifndef FIRMWARE_DATA_H\n#define FIRMWARE_DATA_H\n\n')
h.write(f'#define FIRMWARE_VARS {vc}\n#define FIRMWARE_SIZE {len(cd)}\n\n')
h.write('static const unsigned char firmware_code[FIRMWARE_SIZE] = {\n')
for i in range(0, len(cd), 12):
    h.write('  ' + ', '.join(f'0x{b:02x}' for b in cd[i : i + 12]) + ',\n')
h.write('};\n\n#endif\n')
h.close()
print('OK')
