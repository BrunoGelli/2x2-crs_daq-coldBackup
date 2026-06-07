import warnings
warnings.filterwarnings("ignore")


import argparse
import json
from larpix import packet_v2
from larpix import bitarrayhelper as bah

def main(packet, **kwargs):
        p=packet_v2.Packet_v2()
        p.bits=bah.fromuint(int(packet, 16), nbits=64, endian='little')
        print(p)
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('packet', nargs=1, type=str, help='''packet to parse''')
    args = parser.parse_args()
    
    main(
        *args.packet
    )
