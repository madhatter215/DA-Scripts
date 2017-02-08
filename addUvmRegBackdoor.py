#!/pkg/qct/software/python/3.5.2/bin/python

###############################################################################
# Filename: .py
# Author: cskebriti
# Description: 
#   .
###############################################################################
from pathlib import Path
import regex as re
import io, sys, getopt

p = Path('/prj/qca/cores/wifi/lithium/santaclara/dev01/workspaces/c_ckebri/suhardi')

blockname       = ""
inputBlkFile    = ""
inputSvFile     = ""

def usage():
    print ("\nUsage: {} --block <blockname> --input-blkfile=<file.blk> --input-svfile=<file.sv>\n".format(sys.argv[0]))

try: #Get command line args
    optlist,args = getopt.getopt(sys.argv[1:],"hb:",["help","block=","input-blkfile=","input-svfile="])
    for a,b in optlist:
        if a in ('-h', '--help'):
            usage()
            sys.exit()
        elif a in ('-b', '--block'):
            blockname = b.upper()
        elif a in ('-blkfile', '--input-blkfile'):
            inputBlkFile = Path(b)
        elif a in ('-svfile', '--input-svfile'):
            inputSvFile = Path(b)
        else:
            assert(False), usage()

    if not (blockname and inputBlkFile and inputSvFile):
        raise SystemExit(usage())
    elif (blockname in 'UMAC'):
        raise SystemExit("**System Exit: UMAC not supported **")
    assert(inputBlkFile.is_file() and inputSvFile.is_file())
    outputFile  = inputSvFile.parent / inputSvFile.name.replace('.sv','_OUTPUT.sv')
    SV_FILE     = inputSvFile
    BLK_FILE    = inputBlkFile
    OUTPUT_FILE = outputFile
    print ("Output file = '{}'\n".format(outputFile))


except getopt.GetoptError as e:
    print (e)
    usage()
    sys.exit(2)



## Read in BLK file and parse for register and field names
"""
01   RXDMA_R0_WBM2RXDMA_BUF_RING_BASE_MSB <mac_rxdma_reg_dec: 0x4> 32
02   {                                                               
03     Ring_Size           23:8 NUM DEF=0x0000 RW;                   
04     Ring_Base_Addr_MSB   7:0 NUM DEF=0x00 RW;                     
05   };                                                              
"""
    #Lines 1 and 2
BLK_REGEX_1 = r'^\t({block}_\S+) <mac_{blockLower}_reg.*\n^\t\{{\n'.format(block=blockname, blockLower=blockname.lower())
    #Lines 3 and 4 (or more, pattern occurring at least one line)
BLK_REGEX_2 = r'(?:^\t\t(\S+) .*;\n)+'
    #Line 5 end pattern match
BLK_REGEX_3 = r'^\t\};'
    #Concat the string
BLKpattern  = BLK_REGEX_1 + BLK_REGEX_2 + BLK_REGEX_3


## Read in the file
BLKfileContents = BLK_FILE.read_text()
SVfileContents  = SV_FILE.read_text()


## Compile the regular expression to increase performance
BLKregex = re.compile(BLKpattern, re.MULTILINE)


## Make a dictionary so we can quickly lookup register names for fields
BLKregisterDict = dict()

for m in BLKregex.finditer(BLKfileContents):
    if m.group(1) not in BLKregisterDict:
        BLKregisterDict[m.group(1)] = m.captures(2)
    else: raise
#    print (m.group(1))    #String
#    print (m.captures(2)) #List



myline = r'    this.add_hdl_path_slice({{this.get_name(),"_{BLKfile_fieldname}"}},{UpperFieldname}.get_lsb_pos(),{UpperFieldname}.get_n_bits());' + '\n'


#newFileContents = ""
#buf = io.StringIO(SVfileContents)
#for line in buf.readlines():
#    import pdb; pdb.set_trace()
#    pass

for m in re.finditer(r'^\s*class (?P<SVregister>{block}_\S+) extends uvm_reg;\s+\n.*?(^\s*endfunction)'.format(block=blockname), \
                                                                                    SVfileContents, flags=re.DOTALL|re.MULTILINE):
    mystr = ""
    paragraph = ""
    for field in BLKregisterDict[m.group('SVregister').replace('_MAC_{block}_REG'.format(block=blockname),'')]:
       mystr += myline.format(BLKfile_fieldname = field, UpperFieldname = field.upper())
    
    paragraph = m.group().replace(m.group(2), '')
    SVfileContents = SVfileContents.replace(paragraph + m.group(2), paragraph + mystr + m.group(2))



OUTPUT_FILE.write_text(SVfileContents)

