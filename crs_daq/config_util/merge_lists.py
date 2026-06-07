import argparse
import json
import time
def datetime_now():
	''' Return string with year, month, day, hour, minute '''
	return time.strftime("%Y_%m_%d_%H_%M_%Z")



def main(*files, **kwargs):
        full_list = {}
        for file in files:
            flist={}
            with open(file, 'r') as f: flist=json.load(f)
            
            for key in flist.keys():
                if key=='meta':
                    if not key in full_list.keys():
                        full_list[key]={}

                    for subkey in flist[key].keys():
                        full_list[key][subkey] = flist[key][subkey]
                else:

                    if not key in full_list.keys():
                        full_list[key] = flist[key]
                    else:
                        full_list[key] = list(set(flist[key] + full_list[key]))

        
        fname = 'combined-'+datetime_now()+'.json'
        with open(fname, 'w') as f:
            json.dump(full_list, f, indent=4)

        print('Combined list written to: {}'.format(fname))
        return


                                

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''JSON files to combine at top level''')
    args = parser.parse_args()
    
    main(
        *args.input_files
    )
