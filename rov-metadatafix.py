#!/usr/bin/env python3
"""
ROV METADATAFIX V 1.0 

Full pipeline  Native_run:

  global-metadata.dat
         ↓
  [sub_F1640] Decrypt header
         ↓
  true_header.dat (256 bytes)
         ↓
  [sub_F2004] Rebuild header v29.1
         ↓
  global-metadata-fix.dat (288 bytes)
  
"""

import struct
import sys
import os

try:
    from unicorn import *
    from unicorn.arm64_const import *
except ImportError:
    print("[!] Missing dependency: unicorn")
    print("    Install it with: py -m pip install unicorn")
    sys.exit(1)


# ============================================================
# CONSTANTS
# ============================================================

SIGNATURE = bytes.fromhex('E9 75 83 52 29 56 BD 72')
METADATA_MAGIC = 0xFAB11BAF
METADATA_VERSION = 29

EMU_INPUT_ADDR  = 0x1000001000
EMU_OUTPUT_ADDR = 0x1000002000
EMU_SP_ADDR     = 0x1000009000
EMU_STACK_ADDR  = 0x2000000000
EMU_LR_ADDR     = 0x2000000040
EMU_MAP_BASE    = 0x1000000000
EMU_MAP_SIZE    = 0x10000

BL_MASK = 0xFC000000
BL_OPCODE = 0x94000000

HEADER_SIZE_V29 = 256
HEADER_SIZE_V29_1 = 288
TRANSFORM_SIZE = 256
OUTPUT_DIR = './output'

def print_project_credit():
    print()
    print("              ________________________________")
    print("             /                                /|")
    print("            /       ROV METADATAFIX V 1.0    / |")
    print("           /________________________________/  |")
    print("           |                                |  |")
    print("           |          BY TAR122             |  /")
    print("           |________________________________| /")
    print("           |________________________________|/")
    print("     reverse-engineered with GPT and DeepSeek")
    print()

# ============================================================
# ELF PARSER
# ============================================================

class ELFSegment:
    def __init__(self, p_type, p_flags, p_offset, p_vaddr, p_filesz, p_memsz):
        self.type = p_type
        self.flags = p_flags
        self.offset = p_offset
        self.vaddr = p_vaddr
        self.filesz = p_filesz
        self.memsz = p_memsz


class ELF:
    def __init__(self, data):
        self.data = bytearray(data)
        self.segments = []
        self.dynamic_segments = []
        self.parse()

    def parse(self):
        if self.data[:4] != b'\x7fELF':
            raise ValueError("Not ELF")
        e_phoff = struct.unpack('<Q', self.data[0x20:0x28])[0]
        e_phentsize = struct.unpack('<H', self.data[0x36:0x38])[0]
        e_phnum = struct.unpack('<H', self.data[0x38:0x3A])[0]

        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            ph = self.data[off:off + e_phentsize]
            if len(ph) < 56:
                break
            p_type = struct.unpack('<I', ph[0:4])[0]
            p_flags = struct.unpack('<I', ph[4:8])[0]
            p_offset = struct.unpack('<Q', ph[8:16])[0]
            p_vaddr = struct.unpack('<Q', ph[16:24])[0]
            p_filesz = struct.unpack('<Q', ph[32:40])[0]
            p_memsz = struct.unpack('<Q', ph[40:48])[0]
            if p_type == 1:
                self.segments.append(ELFSegment(
                    p_type, p_flags, p_offset, p_vaddr, p_filesz, p_memsz
                ))
            elif p_type == 2:
                self.dynamic_segments.append(ELFSegment(
                    p_type, p_flags, p_offset, p_vaddr, p_filesz, p_memsz
                ))

    def file_offset_to_va(self, file_offset):
        for seg in self.segments:
            if seg.offset <= file_offset < seg.offset + seg.filesz:
                return seg.vaddr + (file_offset - seg.offset)
        raise ValueError(f"File offset 0x{file_offset:X} is not in a load segment")

    def va_to_file_offset(self, virtual_address):
        for seg in self.segments:
            if seg.vaddr <= virtual_address < seg.vaddr + seg.filesz:
                return seg.offset + (virtual_address - seg.vaddr)
        raise ValueError(f"VA 0x{virtual_address:X} is not backed by the ELF file")

    def dynamic_entries(self):
        for seg in self.dynamic_segments:
            offset = seg.offset
            end = offset + seg.filesz
            while offset + 16 <= end:
                tag, value = struct.unpack_from('<QQ', self.data, offset)
                offset += 16
                if tag == 0:
                    break
                yield tag, value

    def is_executable_va(self, virtual_address):
        return any(
            seg.vaddr <= virtual_address < seg.vaddr + seg.memsz
            and (seg.flags & 1)
            for seg in self.segments
        )

    def apply_relative_relocations(self):
        dynamic = dict(self.dynamic_entries())
        rela_va = dynamic.get(7)
        rela_size = dynamic.get(8, 0)
        rela_ent = dynamic.get(9, 24)
        if not rela_va or rela_ent < 24:
            return 0

        applied = 0
        processed = 0
        rela_offset = self.va_to_file_offset(rela_va)
        for offset in range(rela_offset, rela_offset + rela_size, rela_ent):
            r_offset, r_info, addend = struct.unpack_from(
                '<QQq', self.data, offset
            )
            if (r_info & 0xFFFFFFFF) != 1027:
                continue
            target_offset = self.va_to_file_offset(r_offset)
            struct.pack_into('<Q', self.data, target_offset, addend)
            applied += 1
            processed += 1
            if processed % 100000 == 0:
                print(
                    f"    Materialising relocations: {processed} applied",
                    flush=True,
                )

        if processed:
            print(
                f"    Materialising relocations: {processed} applied",
                flush=True,
            )
        return applied


# ============================================================
# SIGNATURE + TRANSFORMER
# ============================================================

def find_signature(data):
    return data.find(SIGNATURE)


def decode_bl(instr, offset):
    imm26 = instr & 0x03FFFFFF
    if imm26 & 0x02000000:
        imm26 -= 0x04000000
    return offset + (imm26 << 2)


def find_transformer_candidates(elf, sig_offset):
    bl_targets = []
    for i in range(0, 160, 4):
        off = sig_offset + i
        if off + 4 > len(elf.data):
            break
        instr = struct.unpack('<I', elf.data[off:off+4])[0]
        if (instr & BL_MASK) == BL_OPCODE:
            instruction_va = elf.file_offset_to_va(off)
            bl_targets.append((
                decode_bl(instr, instruction_va),
                decode_bl(instr, off),
            ))
    if len(bl_targets) < 3:
        return []
    candidates = []
    for target_va, target_offset in bl_targets[2:]:
        for target in (target_va, target_offset):
            if target not in candidates and elf.is_executable_va(target):
                candidates.append(target)
    return candidates


# ============================================================
# FILE I/O (จำลอง sub_F1CB0, sub_F1ECC)
# ============================================================

def read_file(path):
    """sub_F1CB0: อ่านไฟล์"""
    with open(path, 'rb') as f:
        return f.read()


def write_file(path, data):
    """sub_F1ECC: เขียนไฟล์"""
    with open(path, 'wb') as f:
        f.write(data)


# ============================================================
# UNICORN EMULATION (sub_F1640)
# ============================================================

def emulate_transformer(elf, transformer_va, input_data, output_size):
    """
    รัน transformer ตาม sub_F1640
    
    Args:
        elf: ELF object
        transformer_va: address ของ transformer
        input_data: metadata ที่จะ decrypt
        output_size: ขนาด output (256)
    
    Returns:
        bytes: decrypted header
    """
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)

    # Map ELF segments
    for seg in elf.segments:
        map_addr = seg.vaddr & ~0xFFF
        map_end = (seg.vaddr + seg.memsz + 0xFFF) & ~0xFFF
        map_size = map_end - map_addr
        if map_size == 0:
            continue
        try:
            uc.mem_map(map_addr, map_size, UC_PROT_ALL)
        except UcError:
            continue
        if seg.filesz > 0:
            seg_data = bytes(elf.data[seg.offset:seg.offset + seg.filesz])
            try:
                uc.mem_write(seg.vaddr, seg_data)
            except UcError:
                pass

    relocations = elf.apply_relative_relocations()
    if relocations:
        print(
            f"    Applied {relocations} R_AARCH64_RELATIVE relocations",
            flush=True,
        )

    # Map I/O regions
    print("    Mapping emulator I/O regions...", flush=True)
    try:
        uc.mem_map(EMU_MAP_BASE, EMU_MAP_SIZE, UC_PROT_ALL)
    except UcError:
        pass

    uc.mem_write(EMU_INPUT_ADDR, input_data[:0x1000])
    uc.mem_write(EMU_OUTPUT_ADDR, b'\x00' * output_size)
    print("    Preparing emulator registers...", flush=True)

    try:
        uc.mem_map(EMU_STACK_ADDR, 0x1000, UC_PROT_ALL)
    except UcError:
        pass

    # Set registers according to native sub_F1640.
    uc.reg_write(UC_ARM64_REG_SP, EMU_SP_ADDR)
    uc.reg_write(UC_ARM64_REG_X0, EMU_INPUT_ADDR)
    uc.reg_write(UC_ARM64_REG_X1, EMU_OUTPUT_ADDR)
    uc.reg_write(UC_ARM64_REG_LR, EMU_LR_ADDR)

    last_pc = [None]
    instruction_count = [0]
    memory_fault = [None]

    def trace_instruction(_uc, address, _size, _user_data):
        last_pc[0] = address
        instruction_count[0] += 1
        if instruction_count[0] % 50000 == 0:
            print(
                f"    Transformer progress: {instruction_count[0]} instructions, "
                f"PC=0x{address:X}"
            )

    def trace_invalid_memory(_uc, access, address, size, value, _user_data):
        access_names = {
            UC_MEM_READ_UNMAPPED: "read",
            UC_MEM_WRITE_UNMAPPED: "write",
            UC_MEM_FETCH_UNMAPPED: "fetch",
            UC_MEM_READ_PROT: "read-protected",
            UC_MEM_WRITE_PROT: "write-protected",
            UC_MEM_FETCH_PROT: "fetch-protected",
        }
        name = access_names.get(access, str(access))
        memory_fault[0] = (
            f"Transformer memory fault: {name} address=0x{address:X}, "
            f"size={size}, PC=0x{_uc.reg_read(UC_ARM64_REG_PC):X}"
        )
        return False

    uc.hook_add(UC_HOOK_CODE, trace_instruction)
    uc.hook_add(UC_HOOK_MEM_INVALID, trace_invalid_memory)
    print(f"    Starting transformer at 0x{transformer_va:X}...", flush=True)

    # Run
    try:
        uc.emu_start(
            transformer_va,
            EMU_LR_ADDR,
            timeout=10_000_000,
            count=200000,
        )
        if instruction_count[0] >= 200000:
            raise RuntimeError(
                "Transformer exceeded 200000 instructions; "
                f"last PC=0x{last_pc[0]:X}"
            )
    except UcError as e:
        pc = uc.reg_read(UC_ARM64_REG_PC)
        lr = uc.reg_read(UC_ARM64_REG_LR)
        sp = uc.reg_read(UC_ARM64_REG_SP)
        instr = uc.mem_read(last_pc[0] or pc, 4).hex(' ')
        detail = memory_fault[0] or (
            f"PC=0x{pc:X}, last=0x{(last_pc[0] or pc):X}, "
            f"instr={instr}, LR=0x{lr:X}, SP=0x{sp:X}"
        )
        raise RuntimeError(
            f"Emulation failed: {e}; PC=0x{pc:X}, last=0x{(last_pc[0] or pc):X}, "
            f"instr={instr}, LR=0x{lr:X}, SP=0x{sp:X}; {detail}"
        ) from e

    return bytes(uc.mem_read(EMU_OUTPUT_ADDR, output_size))


# ============================================================
# HEADER REBUILD (sub_F2004)
# ============================================================

def rebuild_header(decrypted_header, original_metadata):
    """
    Rebuild header v29.1 (288 bytes)
    ตาม sub_F2004
    """
    magic, version = struct.unpack('<II', decrypted_header[:8])
    print(f"    Input magic: 0x{magic:08X}, version: {version}")

    # สร้าง header ใหม่ 288 bytes
    new_header = bytearray(HEADER_SIZE_V29_1)

    # Copy magic + version
    new_header[0:8] = decrypted_header[0:8]

    file_size = len(original_metadata)
    entries = [
        list(struct.unpack_from('<II', decrypted_header, 8 + i * 8))
        for i in range(min((len(decrypted_header) - 8) // 8, 31))
    ]
    entries.extend([[0, 0]] * (35 - len(entries)))

    # Protected builds may leave unavailable sections as encrypted garbage.
    # A valid metadata section must fit completely inside the input file.
    for entry in entries:
        data_offset, data_size = entry
        if data_size and (
            data_offset > file_size
            or data_size > file_size - data_offset
        ):
            entry[0] = 0
            entry[1] = 0

    # Recover stringLiteral from the longest region not covered by the
    # sections present in the protected v29 header.
    covered = bytearray(file_size)
    for data_offset, data_size in entries:
        if data_size and 0 <= data_offset <= file_size - data_size:
            covered[data_offset:data_offset + data_size] = b'\x01' * data_size

    best_offset = 0
    best_size = 0
    run_offset = None
    for offset in range(HEADER_SIZE_V29, file_size):
        if covered[offset] == 0:
            if run_offset is None:
                run_offset = offset
        elif run_offset is not None:
            run_size = offset - run_offset
            if run_size > best_size:
                best_offset, best_size = run_offset, run_size
            run_offset = None
    if run_offset is not None and file_size - run_offset > best_size:
        best_offset, best_size = run_offset, file_size - run_offset

    if best_size:
        entries[0] = [best_offset, best_size]

    # These v29.1 sections are absent from the protected header.
    for index in (28, 29, 31, 32, 33, 34):
        entries[index] = [file_size, 0]

    for index, (data_offset, data_size) in enumerate(entries):
        if data_size:
            data_offset += HEADER_SIZE_V29_1 - HEADER_SIZE_V29
        struct.pack_into('<II', new_header, 8 + index * 8,
                         data_offset, data_size)

    # Copy data หลัง header (256 bytes)
    if len(original_metadata) > HEADER_SIZE_V29:
        data_part = original_metadata[HEADER_SIZE_V29:]
    else:
        data_part = b''

    return bytes(new_header) + data_part


# ============================================================
# MAIN PIPELINE (จำลอง Native_run)
# ============================================================

def run_pipeline(lib_path, input_meta_path, output_dir):
    """
    Pipeline ทั้งหมด:
      1. Parse libil2cpp.so
      2. หา transformer
      3. sub_F1640: Decrypt → true_header.dat
      4. sub_F2004: Rebuild → global-metadata-fix.dat
    """
    os.makedirs(output_dir, exist_ok=True)

    step_dec_path = os.path.join(output_dir, 'true_header.dat')
    meta_v29_path = os.path.join(output_dir, 'global-metadata-fix.dat')

    # ============================================================
    # STEP 1: Parse libil2cpp.so
    # ============================================================
    print("[*] STEP 1: Parse libil2cpp.so")
    elf_data = read_file(lib_path)
    print(f"    Size: {len(elf_data)} bytes")

    elf = ELF(elf_data)
    print(f"    Segments: {len(elf.segments)}")

    # ============================================================
    # STEP 2: Locate transformer
    # ============================================================
    print()
    print("[*] STEP 2: Locate transformer")

    sig_offset = find_signature(elf_data)
    if sig_offset < 0:
        raise RuntimeError("Signature not found")
    print(f"    Signature at: 0x{sig_offset:X}")

    transformer_candidates = find_transformer_candidates(elf, sig_offset)
    if not transformer_candidates:
        raise RuntimeError("Transformer not found")
    print("    Transformer candidates: " + ", ".join(
        f"0x{candidate:X}" for candidate in transformer_candidates
    ))

    # ============================================================
    # STEP 3: sub_F1640 — Decrypt metadata header
    # ============================================================
    print()
    print("[*] STEP 3: Decrypt metadata header")

    print(f"    Reading: {input_meta_path}")
    input_metadata = read_file(input_meta_path)
    print(f"    Size: {len(input_metadata)} bytes")

    if len(input_metadata) < TRANSFORM_SIZE:
        raise RuntimeError(f"Metadata too small (< {TRANSFORM_SIZE})")

    print("    Emulating transformer candidates...")
    selected = None
    for candidate in transformer_candidates:
        try:
            candidate_output = emulate_transformer(
                elf, candidate, input_metadata, TRANSFORM_SIZE
            )
        except RuntimeError as error:
            print(f"      0x{candidate:X}: failed ({error})")
            continue
        selected = candidate, candidate_output
        print(f"      0x{candidate:X}: completed")
        break

    if selected is None:
        raise RuntimeError("All transformer candidates failed")
    transformer_va, decrypted = selected
    print(f"    Selected transformer: 0x{transformer_va:X}")

    # The protected header keeps the magic byte modified after decryption.
    decrypted = bytearray(decrypted)
    struct.pack_into('<I', decrypted, 0, METADATA_MAGIC)
    decrypted = bytes(decrypted)

    # เขียน step_dec.dat (เหมือน sub_F1640)
    print(f"    Writing: {step_dec_path}")
    write_file(step_dec_path, decrypted)
    print(f"    Size: {len(decrypted)} bytes")

    # ตรวจสอบ magic
    if len(decrypted) >= 8:
        magic, version = struct.unpack('<II', decrypted[:8])
        print(f"    Magic: 0x{magic:08X}")
        print(f"    Version: {version}")

    # ============================================================
    # STEP 4: sub_F2004 — Rebuild header v29.1
    # ============================================================
    print()
    print("[*] STEP 4: Rebuild header v29.1")

    print(f"    Reading: {step_dec_path}")
    header_data = read_file(step_dec_path)

    print(f"    Rebuilding header...")
    rebuilt = rebuild_header(header_data, input_metadata)

    print(f"    Writing: {meta_v29_path}")
    write_file(meta_v29_path, rebuilt)
    print(f"    Size: {len(rebuilt)} bytes")

    # ============================================================
    # FINAL: Verify
    # ============================================================
    print()
    print("[*] FINAL VERIFICATION")

    check = read_file(meta_v29_path)
    magic, version = struct.unpack('<II', check[:8])

    ok_magic = magic == METADATA_MAGIC
    ok_version = version == METADATA_VERSION

    print(f"    Magic:   0x{magic:08X} {'true' if ok_magic else 'false'}")
    print(f"    Version: {version} {'true' if ok_version else 'false'}")
    print(f"    Size:    {len(check)} bytes")

    if ok_magic and ok_version:
        print()
        print("[+] SUCCESS!")
        print(f"    true_header.dat: {step_dec_path}")
        print(f"    global-metadata-fix.dat: {meta_v29_path}")

    return meta_v29_path


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    print_project_credit()

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <libil2cpp.so> <global-metadata.dat>")
        print()
        print("Example:")
        print(f"  {sys.argv[0]} libil2cpp.so global-metadata.dat")
        sys.exit(1)

    lib_path = sys.argv[1]
    meta_path = sys.argv[2]

    try:
        result = run_pipeline(lib_path, meta_path, OUTPUT_DIR)
        print()
        print(f"[+] Done: {result}")
        print()
        print(f"[+] {result} is ready to dump!")
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()