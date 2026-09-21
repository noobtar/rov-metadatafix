# rov-metadatafix

```text
             ________________________________
           /                                /|
          /        ROV METADATAFIX         / |
         /________________________________/  |
         |                                |  |
         |          BY TAR122             |  /
         |________________________________| /
         |________________________________|/
     reverse-engineered with GPT and DeepSeek
```

**ROV MetadataFix by TAR122**  
*Reverse-engineered with GPT and DeepSeek*

เครื่องมือนี้ใช้ช่วยสร้างไฟล์ metadata ที่มี header แบบ `v29.1` จากไฟล์สองอย่าง:

- `libil2cpp.so` คือไฟล์โปรแกรมของเกม ซึ่งมี code สำหรับถอด header
- `global-metadata.dat` คือไฟล์ metadata ที่ header ถูกป้องกันไว้

ผลลัพธ์หลักคือ:

- `true_header.dat` - header หลังผ่าน transformer ขนาด 256 bytes
- `global-metadata-fix.dat` - metadata ที่สร้าง header ใหม่เป็น v29.1 ขนาด header 288 bytes

> คำเตือน: เครื่องมือนี้เป็นงาน reverse engineering สำหรับไฟล์ที่คุณมีสิทธิ์ใช้งานเท่านั้น

---

## อธิบายแบบง่ายที่สุด

ลองนึกว่า `global-metadata.dat` เป็นกล่องของเล่นที่มีฝาล็อกอยู่

- `libil2cpp.so` เป็นกุญแจและคู่มือเปิดกล่อง
- `transformer` เป็นเครื่องมือที่ถอดฝาล็อก
- `true_header.dat` คือฝาที่ถอดออกมาได้
- `global-metadata-fix.dat` คือกล่องที่เปลี่ยนฝาใหม่ให้ Il2CppDumper อ่านได้

โปรแกรมทำตามลำดับนี้:

```text
libil2cpp.so
    |
    | หา transformer และเตรียม code ใน emulator
    v
global-metadata.dat
    |
    | ถอด header 256 bytes
    v
true_header.dat
    |
    | กู้ section ที่หาย และขยาย header
    v
global-metadata-fix.dat
```

---

## สิ่งที่ต้องติดตั้ง

ต้องใช้ Python และแพ็กเกจ Unicorn:

```bat
py -m pip install unicorn
```

ตรวจสอบว่าใช้งานได้:

```bat
py -c "import unicorn; print(unicorn.__version__)"
```

## ใช้งานบน Termux (Android)

โปรแกรมนี้สามารถลองใช้งานบน Termux ได้ โดยแนะนำให้ใช้ Android/Termux แบบ 64-bit

### 1. ตรวจสอบสถาปัตยกรรม

เปิด Termux แล้วรัน:

```bash
uname -m
```

ควรได้:

```text
aarch64
```

ถ้าเป็น `armv7l` หรือสถาปัตยกรรม 32-bit อาจใช้กับไฟล์ ARM64 และ address ของโปรแกรมนี้ไม่ได้

### 2. ติดตั้ง Python และเครื่องมือที่จำเป็น

วิธีที่สะดวกที่สุดคือวางไฟล์ `install-termux.sh` ไว้ในโฟลเดอร์เดียวกับโปรแกรม แล้วรันคำสั่งเดียว:

```bash
bash install-termux.sh
```

สคริปต์จะอัปเดต Termux ติดตั้งเครื่องมือ build, compile Unicorn 2.1.4 จาก source, สร้าง symlink และตรวจสอบการ import ให้อัตโนมัติ

ถ้าต้องการติดตั้งด้วยตัวเอง ให้รันคำสั่งต่อไปนี้:

```bash
pkg update && pkg upgrade -y
pkg install python -y
pkg install cmake clang make -y
python -m pip install --upgrade pip setuptools wheel
pip install --no-cache-dir --no-binary unicorn unicorn==2.1.4
cd $PREFIX/lib/python3.14/site-packages/unicorn/lib
ln -sf libunicorn.so.2 libunicorn.so
```

ตรวจสอบว่า Unicorn โหลดได้:

```bash
python -c "import unicorn; print('Unicorn:', unicorn.__version__)"
```

ขั้นตอนนี้บังคับให้ compile Unicorn 2.1.4 จาก source เพื่อให้ใช้งานบน Termux ได้ โดย path `python3.14` ต้องตรงกับเวอร์ชัน Python ที่ติดตั้งอยู่ใน Termux

### 3. เปิดสิทธิ์เข้าถึงไฟล์

รันครั้งเดียว:

```bash
termux-setup-storage
```

กดยอมรับ permission จาก Android แล้วไฟล์ใน shared storage จะอยู่ใต้:

```text
~/storage/shared/
```

### 4. เตรียมไฟล์

วางไฟล์เหล่านี้ไว้ในโฟลเดอร์เดียวกัน:

```text
rov-metadatafix.py
libil2cpp.so
global-metadata.dat
```

ตัวอย่างการเข้าโฟลเดอร์:

```bash
cd ~/storage/shared/rov-metadatafix
```

### 5. รันโปรแกรม

ใช้ `python` แทนคำสั่ง `py` ของ Windows:

```bash
python rov-metadatafix.py libil2cpp.so global-metadata.dat
```

ผลลัพธ์จะถูกสร้างในโฟลเดอร์:

```text
./output/
├── true_header.dat
└── global-metadata-fix.dat
```

### ปัญหาที่พบบ่อยบน Termux

- `No module named unicorn` ให้รัน `python -m pip install unicorn`
- `Permission denied` ให้รัน `termux-setup-storage` และอนุญาตสิทธิ์ storage
- โปรแกรมหยุดระหว่าง materialise relocations ให้ตรวจว่า RAM เหลือเพียงพอ เพราะต้องอ่าน ELF ขนาดใหญ่และประมวลผล relocation จำนวนมาก
- `Signature not found` หรือ `Transformer not found` อาจหมายถึง `libil2cpp.so` คนละ build กับ metadata หรือ protection profile ต่างกัน

Termux ไม่ใช่ Windows จึงไม่ใช้ `.exe`, `py` หรือคำสั่ง batch ของ Windows ให้ใช้ `python` และคำสั่ง shell ของ Android แทน

---

## วิธีใช้งาน

เปิด Command Prompt ในโฟลเดอร์เดียวกับสคริปต์ แล้วรัน:

```bat
py rov-metadatafix.py libil2cpp.so global-metadata.dat
```

รูปแบบคำสั่งคือ:

```text
py rov-metadatafix.py <libil2cpp.so> <global-metadata.dat>
```

ผลลัพธ์จะถูกเขียนลงโฟลเดอร์ `./output` ตายตัวเสมอ

ตัวอย่าง:

```bat
py rov-metadatafix.py game/libil2cpp.so game/global-metadata.dat
```

---

## ไฟล์ผลลัพธ์

เมื่อทำงานเสร็จ จะได้ประมาณนี้:

```text
output/
├── true_header.dat
└── global-metadata-fix.dat
```

### `true_header.dat`

ไฟล์นี้มีขนาด 256 bytes โดยเป็น header ที่ผ่าน transformer แล้ว

8 bytes แรกมักมีรูปแบบ:

```text
AF 1B B1 FA 1D 00 00 00
```

อ่านแบบ little-endian:

```text
AF 1B B1 FA = 0xFAB11BAF = metadata magic
1D 00 00 00 = version 29
```

### `global-metadata-fix.dat`

ไฟล์นี้มี header ใหม่ขนาด 288 bytes แล้วต่อด้วยข้อมูลเดิมของ metadata

โดยทั่วไปขนาดไฟล์จะเพิ่มขึ้น 32 bytes:

```text
288 - 256 = 32 bytes
```

---

## โปรแกรมทำงานอย่างไร

## 1. อ่าน ELF segments

`libil2cpp.so` เป็นไฟล์ ELF โปรแกรมจึงอ่าน `PT_LOAD` segments เพื่อรู้ว่า code และ data แต่ละส่วนต้องวางไว้ที่ address ไหน

การแปลงตำแหน่งทำโดยใช้แนวคิดนี้:

```text
virtual_address = segment.vaddr + (file_offset - segment.offset)
```

พูดง่าย ๆ คือ โปรแกรมดูแผนที่ของหนังสือก่อนว่า “ข้อมูลในไฟล์” ต้องไปอยู่ “ช่องไหนใน memory”

---

## 2. หา signature

โปรแกรมค้นหา byte signature นี้ใน `libil2cpp.so`:

```text
E9 75 83 52 29 56 BD 72
```

signature เปรียบเหมือนป้ายชื่อที่บอกว่า transformer อยู่ใกล้ ๆ ตรงนี้

หลังเจอ signature โปรแกรมจะอ่านคำสั่ง ARM64 รอบ ๆ จุดนั้นเพื่อหา `BL` instructions

`BL` หมายถึงการเรียกฟังก์ชันอื่น

---

## 3. คำนวณ transformer address

สำหรับคำสั่ง ARM64 `BL` โปรแกรมแยกเลข target ออกจากคำสั่ง แล้วคำนวณ:

```text
transformer = address_of_BL + (signed_imm26 << 2)
```

ผลอาจมีหลาย candidate เพราะรอบ signature อาจมีหลายคำสั่ง `BL`

โปรแกรมจะลอง candidate ที่อยู่ใน executable segment และเลือกตัวแรกที่ emulator รันจนจบ

> address ที่หาได้ต้องสอดคล้องกับรูปแบบ ELF ของไฟล์นั้น จึงไม่ควรนำ address จากเกมหนึ่งไปใช้กับอีกเกมหนึ่ง

---

## 4. เตรียม ARM64 emulator

โปรแกรมใช้ Unicorn จำลอง CPU ARM64

memory สำคัญที่เตรียมไว้คือ:

| Address | หน้าที่ |
|---|---|
| `0x1000001000` | buffer ของ metadata input |
| `0x1000002000` | buffer ของ header output |
| `0x1000009000` | stack pointer ตาม native code |
| `0x2000000040` | return address |

register ที่ใช้เรียก transformer:

```text
X0 = 0x1000001000
X1 = 0x1000002000
SP = 0x1000009000
LR = 0x2000000040
```

การตั้ง `SP` สำคัญมาก เพราะคำสั่ง ARM64 ในฟังก์ชันมักเก็บค่าชั่วคราวไว้บน stack

---

## 5. Materialise relocations

ELF บางไฟล์เก็บ address บางตัวไว้ในรูป relocation แทนที่จะเก็บ address จริง

โปรแกรมอ่าน `PT_DYNAMIC` และใช้ relocation ชนิด:

```text
R_AARCH64_RELATIVE = 1027
```

จากนั้นนำค่า addend ไปเขียนลง address เป้าหมายก่อนเริ่ม emulation

ใน pseudocode native มี logic แบบเดียวกัน:

```c
if (relocation_type == 1027)
    *(base + relocation_offset) = addend;
```

ถ้าไม่ทำขั้นนี้ transformer อาจอ่าน pointer ผิดและ:

- กระโดดไป address ศูนย์
- เขียน memory ผิดที่
- ทำงานจบแต่ได้ header เสีย

---

## 6. ถอด header

โปรแกรมนำ metadata ช่วงต้นเข้า input buffer แล้วเริ่ม transformer:

```text
input  -> 0x1000001000
output -> 0x1000002000
size   -> 256 bytes
```

เมื่อ transformer ทำงานเสร็จ Python จะอ่าน output 256 bytes และเขียนเป็น:

```text
output\true_header.dat
```

ตัว native มีการเขียน magic `0xFAB11BAF` กลับไปที่ 4 bytes แรกด้วย จึงเห็น bytes แบบ little-endian เป็น:

```text
AF 1B B1 FA
```

---

## 7. สร้าง header v29.1

header เดิมมีขนาด 256 bytes แต่ v29.1 ต้องการ 288 bytes

ความแตกต่างคือ:

```text
288 - 256 = 32 bytes
```

โปรแกรมจึงทำสิ่งต่อไปนี้:

1. อ่าน entries ที่ transformer คืนมา
2. สร้างพื้นที่ตรวจสอบขนาดเท่ากับ metadata ทั้งไฟล์
3. ทำเครื่องหมายว่าช่วงใดถูกใช้ไปแล้ว
4. หา region ที่ยังว่างยาวที่สุด เพื่อกู้ `stringLiteral`
5. ล้าง entry ที่ offset/size อยู่นอกไฟล์
6. เติม entries ที่ขาดเป็น `file_size, 0`
7. เพิ่ม `32` ให้ offset ของ entry ที่มีข้อมูล
8. สร้าง header 288 bytes
9. ต่อข้อมูลเดิมหลัง header 256 bytes

---

## entries คืออะไร

แต่ละ entry มี 8 bytes:

```text
4 bytes แรก = offset
4 bytes ถัดไป = size
```

ตัวอย่าง:

```text
50 BF BE 01 E8 0F 06 00
```

เมื่ออ่านแบบ little-endian:

```text
offset = 0x01BEBF50
size   = 0x00060FE8
```

หมายถึง section หนึ่งเริ่มที่ offset นั้น และมีขนาดตามค่าที่สอง

---

## ทำไมบาง entry กลายเป็นศูนย์

ในบาง build protected header อาจมี bytes ที่ดูเหมือน entry แต่จริง ๆ เป็นข้อมูลเข้ารหัสหรือไม่มี section นั้น

โปรแกรมจะตรวจว่า:

```text
offset ต้องไม่เกินขนาดไฟล์
offset + size ต้องไม่เกินขนาดไฟล์
```

ถ้าไม่ผ่าน จะเปลี่ยนเป็น:

```text
offset = 0
size = 0
```

จึงอาจเห็น:

```text
00 00 00 00 00 00 00 00
```

นี่เป็นการป้องกันไม่ให้ Il2CppDumper อ่านตำแหน่งที่อยู่นอกไฟล์

---

## ทำไม offset ต้องบวก 32

ข้อมูลส่วนเก่าของ metadata เริ่มหลัง header 256 bytes

เมื่อสร้าง header ใหม่เป็น 288 bytes ข้อมูลเดิมจึงเลื่อนไปข้างหน้า 32 bytes

ตัวอย่าง:

```text
offset เดิม = 0x0263371C
offset ใหม่ = 0x0263371C + 0x20
             = 0x0263373C
```

ถ้าไม่บวก 32 Il2CppDumper จะไปอ่านข้อมูลผิดตำแหน่ง

---



## แปล error ที่พบบ่อย

### `Invalid memory write`

แปลว่า code พยายามเขียนไปยัง memory ที่ยังไม่ได้ map

สาเหตุที่พบบ่อย:

- stack ไม่ได้ตั้งค่า
- output pointer ผิด
- segment ของ ELF map ไม่ครบ

### `UC_ERR_EXCEPTION` และ `PC=0x0`

แปลว่า transformer หรือ helper กระโดดไป address ศูนย์

สาเหตุที่พบบ่อย:

- เลือก BL target ผิด
- relocation ยังไม่ถูก materialise
- เรียกฟังก์ชันด้วย context ไม่ครบ

### magic ถูก แต่ยัง dump ไม่ได้

เช่น:

```text
Magic: 0xFAB11BAF
Version: 29
```

อาจยังไม่พอ เพราะ magic/version เป็นแค่ 8 bytes แรก

ต้องตรวจด้วยว่า:

- entries มี offset ถูกต้องหรือไม่
- offset ถูกเลื่อน `+32` หรือไม่
- entries ที่ไม่มีถูกตั้งเป็นศูนย์หรือไม่
- metadata กับ `libil2cpp.so` เป็นคู่เดียวกันหรือไม่

### `metadata too small`

ไฟล์ metadata สั้นเกินกว่าจะมี header 256 bytes

### `Transformer not found`

signature อาจเปลี่ยนไปใน lib version นั้น หรือไฟล์ไม่ใช่ build/profile ที่สคริปต์รองรับ

---

## ข้อจำกัด

สคริปต์นี้ไม่ได้รองรับทุกเกมและทุก version แบบอัตโนมัติ 100%

เหตุผลคือแต่ละ build อาจมี:

- signature ต่างกัน
- transformer อยู่คนละตำแหน่ง
- layout ของ metadata ต่างกัน
- relocation ต่างกัน
- จำนวน section ต่างกัน
- calling context ต่างกัน

โค้ดปัจจุบันรองรับแนวทางของ native flow ที่วิเคราะห์ไว้ โดยเฉพาะ:

- ELF/ARM64
- `R_AARCH64_RELATIVE`
- protected metadata ที่ต้องถอด header 256 bytes
- การ rebuild เป็น v29.1 ขนาด 288 bytes

ถ้าใช้กับ build อื่นแล้วไม่ได้ ให้ตรวจตามลำดับนี้:

```text
1. metadata เป็นคู่กับ libil2cpp.so หรือไม่
2. เจอ signature หรือไม่
3. transformer candidate ถูกหรือไม่
4. relocation ถูก apply หรือไม่
5. output ของ transformer มี magic/version ถูกหรือไม่
6. entries อยู่ภายในขนาดไฟล์หรือไม่
7. offset ถูกเลื่อนตามขนาด header หรือไม่
```

---

## หลักการอ่าน hex แบบ little-endian

คอมพิวเตอร์มักเก็บเลขหลาย byte โดยเอา byte น้อยไว้ก่อน

ตัวอย่าง:

```text
AF 1B B1 FA
```

ไม่ได้อ่านเป็น `0xAF1BB1FA`

แต่ต้องย้อนลำดับเป็น:

```text
0xFAB11BAF
```

อีกตัวอย่าง:

```text
84 5A 63 02
```

แปลเป็น:

```text
0x02635A84
```

การเข้าใจ little-endian สำคัญมาก เพราะ offset และ size ใน metadata เกือบทั้งหมดเก็บในรูปแบบนี้

---

## สรุปแบบเด็กอนุบาล

```text
1. หาเครื่องมือเปิดกล่อง
2. วางเครื่องมือลงในคอมพิวเตอร์จำลอง
3. ใส่ metadata เข้าไป
4. ให้เครื่องมือเปิดฝา
5. ตรวจว่าฝาและป้ายเลขถูกไหม
6. หาเลขตำแหน่งของของเล่นแต่ละชิ้น
7. ทำฝาใหม่ให้ใหญ่ขึ้น
8. เอาข้อมูลเดิมมาต่อท้าย
9. ส่งกล่องใหม่ให้ Il2CppDumper อ่าน
```

ถ้าส่วนใดส่วนหนึ่งผิด กล่องจะดูเหมือนเปิดได้ แต่ Il2CppDumper จะยังอ่านของข้างในไม่ได้
