"""Reproduce the study prefix without downloading the entire multi-GB ZIP."""
import argparse
from pathlib import Path
from struct import unpack_from
from urllib.request import Request, urlopen
from zlib import decompressobj

URL="https://www.kaggle.com/api/v1/datasets/download/dilwong/flightprices"
CHUNK=4*1024*1024
COUNT=96


def unpack(output, parts=None):
    decoder=decompressobj(-15)
    tail=b""
    with output.open("wb") as out:
        for i in range(COUNT):
            start=i*CHUNK
            if parts is not None:
                raw=(parts/f"expedia-{i:02}.part").read_bytes()
            else:
                req=Request(URL,headers={"Range":f"bytes={start}-{start+CHUNK-1}"})
                with urlopen(req,timeout=120) as r:
                    if not r.headers.get("Content-Range","").startswith(f"bytes {start}-{start+CHUNK-1}/"):
                        raise RuntimeError("Download server did not honor the requested range.")
                    raw=r.read()
            if len(raw)!=CHUNK:
                raise ValueError("Incomplete archive block")
            if i==0:
                filename_len,extra=unpack_from("<HH",raw,26)
                if raw[:4]!=b"PK\x03\x04" or raw[30:30+filename_len]!=b"itineraries.csv" or unpack_from("<H",raw,8)[0]!=8:
                    raise ValueError("Archive layout changed.")
                raw=raw[30+filename_len+extra:]
            decoded=tail+decoder.decompress(raw)
            last=decoded.rfind(b"\n")+1
            out.write(decoded[:last])
            tail=decoded[last:]


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("output",type=Path)
    parser.add_argument("--parts",type=Path)
    args=parser.parse_args()
    unpack(args.output,args.parts)
