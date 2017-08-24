#!/pkg/qct/software/python/3.5.2/bin/python

###############################################################################
# Filename: addHdlPathSlice.py
# Author: cskebriti
# Description: 
#   Reads in RDL file and builds a dictionary with key/value pairs of 
# register names and fields (string/list) and adds hdl_path_slice to .sv
# file for each field inside the class definition. Special handling is done
# for n-Array registers and hdl_path_slice is added outside the class 
# definition within the for-loop. The script guards against any register
# defined as "extern" in the RDL file and against register names with
# 'reserved' keywords within the name. Guarded registers should not get
# hdl_path_slice generated within the .sv file. 
#
"""
Assumptions: 
 a) all registers defined in RDL are found in the addrmap of the RDL file also
 b) n-array registers have only one (1) field
 c) input files (rdl, sv) have proper indentation with spaces (no tabs)
 
"""
###############################################################################
import sys, os
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import io, getopt
from pathlib import Path
##
# Setup path to find packages for imports
if '/prj/helium_tools/python/lib/python3.5/site-packages' not in sys.path:
    sys.path.append('/prj/helium_tools/python/lib/python3.5/site-packages')
if '/pkg/qct/software/python/3.5.2' not in sys.path:
    sys.path.append('/prj/helium_tools/python/lib/python3.5/site-packages')
import regex as re
##########################################

#Debug option default value; override accepted from command line
DEBUG = 0

#################################################################
#Gloabal Variables: these get set upon calling getArgs()
blockname       = "" #String
SV_FILE         = "" #Becomes type 'pathlib.Path'
BLK_FILE        = "" #Becomes type 'pathlib.Path'
RDL_FILE        = "" #Becomes type 'pathlib.Path'
OUTPUT_FILE     = "" #Becomes type 'pathlib.Path'

#Never change; these are templates to be filled for adding hdl path slice for each register into the SV file
addHdl = r'    this.add_hdl_path_slice({{"{RDLreg}", "_{fieldname}"}},{upperFieldname}.get_lsb_pos(),{upperFieldname}.get_n_bits());' + '\n'
addHdl2= r'      {nReg}_N[x].add_hdl_path_slice($sformatf("{reg}%0d_{field}",x),{nReg}_N[x].{field}.get_lsb_pos(),{nReg}_N[x].{field}.get_n_bits());' + '\n'
'''
ex. addHdl: this.add_hdl_path_slice({"REO_R0_General_Enable ","_reo_enable"},REO_ENABLE.get_lsb_pos(),REO_ENABLE.get_n_bits());
'''
#List of keywords to guard against. Reserved fields do not get hdl_path_slice
nonQualifiedKeywords = 'reserved, rsvd, spare, dbug'.split(', ')


######################################################################
#Global variables, these are mutable and they change
RDLregisterDict     = dict() #Make a dictionary so we can quickly lookup register names for fields

XNREG_List          = list()
NREG_List           = list()
REG_List            = list()
XREG_List           = list()


##############################################################################################
# Define local functions:
##############################################################################################
def usage():
    print ("\nUsage: {} --block <blockname> --input-blkfile=mac_<block>_reg.blk --input-svfile=MAC_<BLOCK>_REG.sv \
--input-rdlfile=mac_<block>_reg.rdl\n".format(sys.argv[0]))

def getArgs():
    inputBlkFile    = ""
    inputSvFile     = ""
    inputRdlFile    = ""
    global blockname, SV_FILE, BLK_FILE, RDL_FILE, OUTPUT_FILE, DEBUG, BOOL_MAC_BLK_REG_SUFFIX
    try: #Get command line args
        optlist,args = getopt.getopt(sys.argv[1:],"hbd:",["help","block=","input-blkfile=","input-svfile=","input-rdlfile=","debug=",])
        for a,b in optlist:
            if a in ('-h', '--help'):
                usage()
                sys.exit()
            elif a in ('-b', '--block'):
                blockname = b.upper()
            elif a in ('-blkfile', '--input-blkfile'):
                inputBlkFile    = Path(b)
                print (inputBlkFile)
            elif a in ('-svfile', '--input-svfile'):
                inputSvFile     = Path(b)
                print (inputSvFile)
            elif a in ('-rdlfile', '--input-rdlfile'):
                inputRdlFile    = Path(b)
                print (inputRdlFile)
            elif a in ('-d', '--debug'):
                DEBUG = int(b)
            else:
                assert(False), usage()

        if not (blockname and inputBlkFile and inputSvFile and inputRdlFile):
            raise SystemExit(usage())
        elif (blockname in 'UMAC'):
            raise SystemExit("**System Exit: UMAC not supported **")
        
        #Input SV and Blk files mandatory, assert both files exists
        assert(inputBlkFile.is_file() and inputSvFile.is_file() and inputRdlFile.is_file())

        ####################################################################################
        #If DEBUG set (--debug=1), do not clobber the input .sv file; default is to clobber
        outputFile  = \
        inputSvFile.parent / inputSvFile.name.replace('.sv','_OUTPUT.sv') if DEBUG \
        else inputSvFile
        ##########################
        #Assign to globals########
        SV_FILE     = inputSvFile
        BLK_FILE    = inputBlkFile
        RDL_FILE    = inputRdlFile
        OUTPUT_FILE = outputFile
        print ("Output file = '{}'\n".format(outputFile))
        
        ########################################################################################
        #Do some checking to see whether class names in .sv file will have suffix 
        # "*MAC_<Block>_REG" by looking at the input filename
        BOOL_MAC_BLK_REG_SUFFIX = True if re.search("MAC_{block}_REG".format(block=blockname), inputSvFile.name) else False
        ##########

    except getopt.GetoptError as e:
        print (e)
        usage()
        sys.exit(2)





##############################################################################################
# Define parsing regular expressions of input files: a)RDL_FILE, b)SV_FILE
##############################################################################################


##############################
##RDL_FILE
##############################

#Sample snippit of an RDL file to build dictionary of register/fields
'''
reg REO_R0_RXDMA2REO0_RING_BASE_MSB {
    name     = "REO_R0_RXDMA2REO0_RING_BASE_MSB";
    desc     = "Ring Definition register set";
    regwidth = 32;

    field {
        name  = "Ring_Base_Addr_MSB[7:0]";
        sw = rw; hw = r;
        reset = 0x0;
        desc  = "Upper 8 bit byte address of the Base Address of the Ring.";
    } Ring_Base_Addr_MSB[7:0];
    field {
        name  = "Ring_Size[23:8]";
        sw = rw; hw = r;
        reset = 0x0;
        desc  = "Ring Size. Unit is No. of words. (1 word = 4bytes). The minimum is 16 words  the maximum is 2**16-1 words";
    } Ring_Size[23:8];
};
'''
RDLpattern = \
                   r'^reg (?P<RDL_REGISTER>{block}_\S+)\s*{{\n' \
                 + r'(?:.*?\n)*?' \
                 + r'(^\s*field\s*{{\n\s*name\s*=\s*"\s*(?P<FIELD>\w+).*?";\n(?:.*?\n)*?^\s*}}\s*(?P=FIELD)\s*[\[\]:0-9]*\s*;\n)+' \
                 + r'^}};'
###
"""
>>> m.group('RDL_REGISTER')
'REO_R0_RXDMA2REO0_RING_BASE_MSB'
>>> m.captures('FIELD')
['Ring_Base_Addr_MSB[7:0]', 'Ring_Size[23:8]']
>>> m.captures('FIELD')[0].split('[')[0]
'Ring_Base_Addr_MSB'
"""
###


##Sample snippit of an RDL file along with regex for parsing to find externally defined registers and n-Array registers
#
'''
addrmap mac_hwsch_reg {
    name = "mac_hwsch_reg Config Register Map";
             HWSCH_R0_DIFS_LIMIT_1_0                  HWSCH_R0_DIFS_LIMIT_1_0                            @0x0;
             HWSCH_R0_DIFS_LIMIT_3_2                  HWSCH_R0_DIFS_LIMIT_3_2                            @0x4;
             HWSCH_R0_DIFS_LIMIT_5_4                  HWSCH_R0_DIFS_LIMIT_5_4                            @0x8;
    external HWSCH_R2_SCH2TQM_RING_HP                 HWSCH_R2_SCH2TQM_RING_HP                           @0x5090;
    external HWSCH_R2_SCH2TQM_RING_TP                 HWSCH_R2_SCH2TQM_RING_TP                           @0x5094;
             HWSCH_R0_GENERIC_TIMERS                  HWSCH_R0_GENERIC_TIMERS[32]                        @0x2f8;
             HWSCH_R0_GENERIC_TIMERS_MODE             HWSCH_R0_GENERIC_TIMERS_MODE                       @0x378;
             HWSCH_R0_WC_SOC_RFF_TSF_OFFSETS          HWSCH_R0_WC_SOC_RFF_TSF_OFFSETS[4]                 @0x37c;
    external HWSCH_R0_TSF_UPDATE                      HWSCH_R0_TSF_UPDATE                                @0x38c;
    external HWSCH_FAKE                               HWSCH_FAKE [2]                                     @0x38c;
};
'''
XNREG_PATTERN     = r'^\s+external \S+\s+(?P<XNREG>{block}_\w+(?=(?:\s)*\[))'
NREG_PATTERN      = r'^\s+(?!external )\S+\s+(?P<NREG>{block}_\w+(?=(?:\s)*\[))'
REG_PATTERN       = r'^\s+(?!external )\S+\s+(?P<REG>{block}_\w+) (?!\])\s*@'
XREG_PATTERN      = r'^\s+external \S+\s+(?P<XREG>{block}_\w+) (?!\[)\s*@'
"""
"""


##############################
##SV_FILE
##############################
#System Verilog file snippet where we want to find classes that extend uvm_reg to append the add_hdl_path_slice
#for each field in the register
'''
14376 class RXDMA_R2_RXDMA2FW_RING_TP_MAC_RXDMA_REG extends uvm_reg;
14377 
14378   rand uvm_reg_field TAIL_PTR;
14379 
14380   virtual function void build();
14381     TAIL_PTR = uvm_reg_field::type_id::create("TAIL_PTR");
14382     TAIL_PTR.configure(this, 16, 0, "RW", 0, `UVM_REG_DATA_WIDTH'h00000000>>0, 1, 1, 1);
14389     this.add_hdl_path_slice({this.get_name(),"_Tail_Ptr"},TAIL_PTR.get_lsb_pos(),TAIL_PTR.get_n_bits());
14390   endfunction
'''
SVpattern1 = r'^\s*class (?P<SVregister>{regRoot}(?P<SUFFIX>_\w+)) extends uvm_reg;\s+\n.*?(?P<END>^\s*endfunction)'
#m.group('SVregister')
#m.group('SUFFIX')
#m.group('END')
#
###############################################################
#System Verilog file (special handling for register N array)
#Note: this is what we want the output to look like (line #8480)
#      only for special N array registers
'''
BEFORE:
=======
     for(int x=0; x<=11; x++)
     begin
       uvm_reg_addr_t laddr='h270+'h4*x;
       TXPCU_<Reg>_N[x].configure(this, null);
       TXPCU_<Reg>_N[x].build();
     end
AFTER:
=======
     for(int x=0; x<=11; x++)
     begin
       uvm_reg_addr_t laddr='h270+'h4*x;
       TXPCU_<Reg>_N[x].configure(this, null);
       TXPCU_<Reg>_N[x].build();
       TXPCU_<Reg>_N[x].add_hdl_path_slice($sformatf("TXPCU_<Reg>%0d_VALUE",x),TXPCU_<Reg>_N[x].VALUE.get_lsb_pos(),TXPCU_<Reg>_N[x].VALUE.get_n_bits());
     end
'''
SVpattern2 = \
      r'^\s*for.*\n\s*begin\n\s*uvm_reg_addr_t.*;\n' \
    + r'\s+{nReg}_N\[.*configure.*\n' \
    + r'\s+{nReg}_N\[.*build.*\n' \
    + r'(?P<END>\s*end)'







########################################################################
# Main: Start of Program                                               #
########################################################################
if 'main' in __name__: print ("\n\n\t**Start of Program**\n")


###############
# Call getArgs: populates input 
#filenames/paths and blockname
getArgs()



#################
##Regex Patterns:
##
RDLpattern  = RDLpattern.format(block=blockname)
#
XNREG_PATTERN     = XNREG_PATTERN.format(block=blockname)
NREG_PATTERN      = NREG_PATTERN.format(block=blockname)
REG_PATTERN       = REG_PATTERN.format(block=blockname)
XREG_PATTERN      = XREG_PATTERN.format(block=blockname)


## Compile most used regular expressions to increase performance
RDLregex = re.compile(pattern=RDLpattern, flags=re.MULTILINE)


#######################################################################
## Read contents of input files (Note: files open/close through the API)
##
SVfileContents  = SV_FILE.read_text()
RDLfileContents = RDL_FILE.read_text(encoding='ISO-8859-1')



##################################################################
## Parse RDL file and build dictionary of register/field pairs
###
for m in RDLregex.finditer(RDLfileContents):
    key = m.group('RDL_REGISTER')
    if key not in RDLregisterDict:
        RDLregisterDict[key] = m.captures('FIELD')
#        RDLregisterDict[key] = list(regs for regs in map(lambda x: x.split('[')[0], m.captures('FIELD')))

#import pdb; pdb.set_trace()
##################################################################
## Parse RDL file and build a list of registers 
#   that are externally defined (**extern**)
#   and/or n-Array registers
m = re.search(r'^addrmap .*?^};', RDLfileContents, flags=re.MULTILINE|re.DOTALL)
mylist = m.group().split('\n')
i = -1
for x in mylist:
    i += 1
    if bool(re.match(XNREG_PATTERN, x)):
        m = re.match(XNREG_PATTERN, x)
        if DEBUG > 1: print ("{} XNREG: '{}'\n{}".format(i, m.group('XNREG'), x))
        XNREG_List.append(m.group('XNREG'))
    elif bool(re.match(NREG_PATTERN, x)):
        m = re.match(NREG_PATTERN, x)
        if DEBUG > 1: print ("{} NREG: '{}'\n{}".format(i, m.group('NREG'), x))
        NREG_List.append(m.group('NREG'))
    elif bool(re.match(REG_PATTERN, x)):
        m = re.match(REG_PATTERN, x)
        if DEBUG > 1: print ("{} REG: '{}'\n{}".format(i, m.group('REG'), x))
        REG_List.append(m.group('REG'))
    elif bool(re.match(XREG_PATTERN, x)):
        m = re.match(XREG_PATTERN, x)
        if DEBUG > 1: print ("{} XREG: '{}'\n{}".format(i, m.group('XREG'), x))
        XREG_List.append(m.group('XREG'))
    else: 
        if DEBUG > 1: print ("{} NO MATCH: '{}'".format(i, x))




##################################################################
## Helper function for programs below
###
def checkForReservedNames(val):
    reservedVals = list(x for x in nonQualifiedKeywords if re.search(x, val, flags=re.IGNORECASE))
    if (DEBUG > 1 and reservedVals):
        print ("\tcheckForReservedNames: ", reservedVals, " keyword found in the value: ", val)
    return bool(reservedVals)
        

##################################################################
## Add hdl_path_slice to SV file inside 'class' definition for 
# each field in every register **except** for 'external' registers
# and registers/fields with reserved names. 
# Note that n-Array registers  will process those later.
for reg in REG_List:
    mystr            = ""
    paragraph        = ""
    m                = ""
    #Check that the field name does not contain any reserved keywords
    if (checkForReservedNames(reg)):
        print ("Skipping register '{}' since it contains non-qualified keywords in name".format(reg))
        continue
    
    for m in re.finditer(SVpattern1.format(regRoot=reg), SVfileContents, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE):
#    if m:
        try:
            #Verify we found the full register name, not a partial
            if not(  (m.group('SUFFIX') == "_MAC_{}_REG".format(blockname))  or  (m.group('SUFFIX') == "_{}_REG".format(blockname))  ):
                if DEBUG > 1: print (reg, m.group('SUFFIX'))
                continue #next loop iteration on 'm'

            for field in RDLregisterDict[reg]:

                if not(checkForReservedNames(field)) and bool(re.search("rand uvm_reg_field {};".format(field), m.group(), flags=re.IGNORECASE)):
                    mystr += addHdl.format(RDLreg=reg, fieldname=field, upperFieldname=field.upper())
                else:
#                    import pdb; pdb.set_trace()
                    print ("Skipping field '{}' in register '{}' since the name either contains non-qualified keywords or the field was not found in the sv class".format(
                          field,reg))
                    #continue #next loop iteration for 'field' in RDLregisterDict[reg]


            paragraph = m.group().replace(m.group('END'), '')
            SVfileContents = SVfileContents.replace(paragraph + m.group('END'), paragraph + mystr + m.group('END'))
        
        except KeyError as err:
#            import pdb; pdb.set_trace()
            print ("Key error: \n\tRegister not found in RDL: '{}'".format(err))

    else:
        pass#print ("REG not found: ", reg)



###################################################################
## Add hdl_path_slice to SV file for n-Array registers found in 
# RDL file. Excludes 'external' registers and registers/fields 
# with reserved names
for reg in NREG_List:
    mystr            = ""
    paragraph        = ""
    m                = ""

    #Check that the field name does not contain any reserved keywords
    if (checkForReservedNames(reg)):
        print ("Skipping n-Array register '{}' since it contains non-qualified keywords in name".format(reg))
        continue #next loop for 'reg' in NREG_List

    m = re.search(SVpattern2.format(nReg=reg), SVfileContents, flags=re.MULTILINE|re.IGNORECASE)
    if m:
        try:

            for field in RDLregisterDict[reg]:

                if not (checkForReservedNames(field)):
                    mystr += addHdl2.format(nReg    = reg, \
                                            reg     = reg, \
                                            field   = field.upper())
                else:
                    print ("Skipping n-Array field '{}' in register '{}' since it contains non-qualified keywords in name".format(field,reg))


            paragraph = m.group().replace(m.group('END'), '')
            SVfileContents = SVfileContents.replace(paragraph + m.group('END'), paragraph + mystr + m.group('END'))
        
        except KeyError as err:
            print ("Key error: \n\tN-Array register not found in RDL: '{}'".format(err))

    else:
        print ("NREG not found: ", reg)





#import pdb; pdb.set_trace()

###################################################################
# Write out the file
OUTPUT_FILE.write_text(SVfileContents)
###
