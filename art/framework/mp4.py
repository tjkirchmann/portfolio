"""Pure-Python MP4 faststart rewrite and MP4 / WebM probing (no ffprobe needed)."""
import struct

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf"}


def boxes(buf, start=0, end=None):
    end = len(buf) if end is None else end
    i = start
    while i + 8 <= end:
        size, typ = struct.unpack(">I4s", buf[i:i + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - i
        yield typ, i, hdr, size
        i += size


def find(buf, path, start=0, end=None):
    """All boxes matching a path like [b'moov', b'trak', ...]."""
    out = []
    for typ, i, hdr, size in boxes(buf, start, end):
        if typ == path[0]:
            if len(path) == 1:
                out.append((i, hdr, size))
            else:
                out += find(buf, path[1:], i + hdr, i + size)
    return out


def _shift_offsets(moov, delta, start, end):
    for typ, i, hdr, size in boxes(moov, start, end):
        if typ in CONTAINERS:
            _shift_offsets(moov, delta, i + hdr, i + size)
        elif typ == b"stco":
            n = struct.unpack(">I", moov[i + 12:i + 16])[0]
            for k in range(n):
                p = i + 16 + 4 * k
                v = struct.unpack(">I", moov[p:p + 4])[0] + delta
                moov[p:p + 4] = struct.pack(">I", v)
        elif typ == b"co64":
            n = struct.unpack(">I", moov[i + 12:i + 16])[0]
            for k in range(n):
                p = i + 16 + 8 * k
                v = struct.unpack(">Q", moov[p:p + 8])[0] + delta
                moov[p:p + 8] = struct.pack(">Q", v)


def faststart(src, dst):
    with open(src, "rb") as f:
        buf = f.read()
    top = list(boxes(buf))
    order = [t for t, *_ in top]
    if order.index(b"moov") < order.index(b"mdat"):
        with open(dst, "wb") as f:
            f.write(buf)
        return
    moov_t = next(b for b in top if b[0] == b"moov")
    moov = bytearray(buf[moov_t[1]:moov_t[1] + moov_t[3]])
    _shift_offsets(moov, len(moov), 8, len(moov))
    out = bytearray()
    for typ, i, hdr, size in top:
        if typ == b"moov":
            continue
        if typ == b"mdat":
            out += moov
        out += buf[i:i + size]
    with open(dst, "wb") as f:
        f.write(out)


def _ue(bits, pos):
    zeros = 0
    while bits[pos] == 0:
        zeros += 1
        pos += 1
    pos += 1
    val = 0
    for _ in range(zeros):
        val = (val << 1) | bits[pos]
        pos += 1
    return (1 << zeros) - 1 + val, pos


def _sps_chroma(sps):
    raw = bytearray()
    i = 0
    while i < len(sps):  # strip emulation prevention bytes
        if i + 2 < len(sps) and sps[i] == 0 and sps[i + 1] == 0 and sps[i + 2] == 3:
            raw += sps[i:i + 2]
            i += 3
        else:
            raw.append(sps[i])
            i += 1
    profile = raw[1]
    bits = [(b >> (7 - k)) & 1 for b in raw[4:] for k in range(8)]
    _, pos = _ue(bits, 0)
    chroma = 1
    if profile in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
        chroma, pos = _ue(bits, pos)
    return profile, chroma


def probe_mp4(path):
    with open(path, "rb") as f:
        buf = f.read()
    order = [t.decode() for t, *_ in boxes(buf)]
    info = dict(top_level=order, faststart=order.index("moov") < order.index("mdat"))
    i, h, s = find(buf, [b"moov", b"mvhd"])[0]
    ver = buf[i + h]
    if ver == 1:
        ts, dur = struct.unpack(">IQ", buf[i + h + 20:i + h + 32])
    else:
        ts, dur = struct.unpack(">II", buf[i + h + 12:i + h + 20])
    info["duration"] = dur / ts
    i, h, s = find(buf, [b"moov", b"trak", b"tkhd"])[0]
    w, hh = struct.unpack(">II", buf[i + s - 8:i + s])
    info["width"], info["height"] = w >> 16, hh >> 16
    i, h, s = find(buf, [b"moov", b"trak", b"mdia", b"minf", b"stbl", b"stsz"])[0]
    info["frames"] = struct.unpack(">I", buf[i + h + 8:i + h + 12])[0]
    info["fps"] = round(info["frames"] / info["duration"], 3) if info["duration"] else None
    i, h, s = find(buf, [b"moov", b"trak", b"mdia", b"minf", b"stbl", b"stsd"])[0]
    entry = buf[i + h + 8:i + s]
    codec = entry[4:8].decode()
    info["codec"] = codec
    if codec == "avc1":
        k = entry.find(b"avcC")
        avcc = entry[k + 4:]
        info["profile_idc"] = avcc[1]
        info["level_idc"] = avcc[3]
        n_sps = avcc[5] & 0x1F
        ln = struct.unpack(">H", avcc[6:8])[0]
        sps = avcc[8:8 + ln]
        prof, chroma = _sps_chroma(sps)
        info["profile"] = {66: "Baseline", 77: "Main", 100: "High"}.get(prof, str(prof))
        info["chroma"] = {0: "4:0:0", 1: "4:2:0 (yuv420p)", 2: "4:2:2", 3: "4:4:4"}[chroma]
    return info


def _ebml_vint(buf, i, strip=True):
    b = buf[i]
    n = 1
    mask = 0x80
    while n <= 8 and not (b & mask):
        mask >>= 1
        n += 1
    val = b & (mask - 1) if strip else b
    for k in range(1, n):
        val = (val << 8) | buf[i + k]
    return val, n


def probe_webm(path):
    """Minimal EBML walk for codec, size, frame count and duration."""
    with open(path, "rb") as f:
        buf = f.read()
    info = {}
    MASTER = {0x18538067, 0x1654AE6B, 0xAE, 0xE0, 0x1549A966, 0x1F43B675, 0xA0, 0x1A45DFA3}
    frames = 0
    timescale = 1000000
    dur = None

    def walk(i, end):
        nonlocal frames, timescale, dur
        while i < end:
            eid, n = _ebml_vint(buf, i, strip=False)
            size, m = _ebml_vint(buf, i + n)
            d = i + n + m
            if size == (1 << (7 * m)) - 1:  # unknown size
                size = end - d
            if eid in MASTER:
                walk(d, min(d + size, end))
            elif eid == 0x86:
                info["codec"] = buf[d:d + size].decode()
            elif eid == 0xB0:
                info["width"] = int.from_bytes(buf[d:d + size], "big")
            elif eid == 0xBA:
                info["height"] = int.from_bytes(buf[d:d + size], "big")
            elif eid == 0x2AD7B1:
                timescale = int.from_bytes(buf[d:d + size], "big")
            elif eid == 0x4489:
                dur = struct.unpack(">f" if size == 4 else ">d", buf[d:d + size])[0]
            elif eid in (0xA3, 0xA1):
                frames += 1
            i = d + size

    walk(0, len(buf))
    info["frames"] = frames
    if dur is not None:
        info["duration"] = round(dur * timescale / 1e9, 3)
    return info
