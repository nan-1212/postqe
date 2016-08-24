#encoding: UTF-8

import time, sys
import numpy as np
from struct import *

################################################################################
# Readers of binary files.
#
# Warning: all the following functions for reading binary files are platform 
# dependent and may not work properly. Note that the long term solution is to 
# use hdf5 format.
def read_line(f):
    """
    Read a line from a binary file. End character must be b'\n'
    """
    line = b''
    byte = f.read(1)
    while (byte != b'\n'):
        line += byte
        byte = f.read(1)
            
    return line


def read_n_real_numbers(f,nr1,nr2,kind=8):
    """
    Read n real numbers from a binary (fortran) file section. Extra characters
    are present in the file and discarded. Potentially troublesome...
    """
    a = np.zeros((nr1,nr2))
    byte = f.read(12)    # discard the first 12 bytes (extra info written by iotk/fortran)
    for j in range(0,nr2):
        for i in range(0,nr1):
            byte = f.read(kind)    
            x = unpack('d',byte)  
            a[i,j] = x[0]     # x is a list, take the first element only
        
    return a


def get_info(info_line):
    """
    Get nr1, nr2, nr3 from line <INFO...>
    """
    import re
    
    pat = re.compile(r'nr\d="\d+"')    
    info_line_nrx = pat.findall(info_line)
    
    nr = np.zeros(3,dtype=int)
    for i in range(0,len(info_line_nrx)):
        nr[i] = info_line_nrx[i].split("\"")[1]
    
    return nr[0], nr[1], nr[2]



def read_charge_file_iotk(fname):
    """
    Read a binary charge file written with QE and iotk. Warning: platform dependent,
    use hdf5 format when available
    """
 
    tempcharge = []
    
    with open(fname, "rb") as f:
        line = b''
        while (line!=b'  <CHARGE-DENSITY>'):    # skip lines till the <CHARGE-DENSITY> tag is found
            line = read_line(f)
            
        discard = read_line(f)  # discard binary line here
        line = read_line(f)     # this is the line <INFO nr1=.. />
        info_line = line.decode('utf-8')
        nr1, nr2, nr3 = get_info(info_line)
        #print ("Reading from charge file: nr1= ",nr1,"nr2= ",nr2,"nr3= ",nr3)

        # data are grouped in nr1*nr2 sequential reals in the charge file, each
        # starting with <z.1, <z.2, etc. tag and ending with a corresponding
        # </z.1>, </z.2> containing extra information...
        charge = np.zeros((nr1,nr2,nr3))
        for i in range(0,nr3):   
            discard = read_line(f)
            line = read_line(f)     # this is the line <z.1 type="real" size="2025" kind="8"> or similar
        
            temp = read_n_real_numbers(f,nr1,nr2)
            charge[:,:,i] = temp
            
            discard = read_line(f)
            line = read_line(f)     # this is end tag </z.1>
        
    return charge


def read_wavefunction_file_iotk(fname):
    """
    To be implemented.
    """

    return None


def read_charge_file_hdf5(fname):
    """
    Reads an hdf5 charge file written with QE. nr1, nr2, nr3 (the dimensions of
    the charge k-points grid) are read from the charge file.
    """
 
    import h5py
    
    f = h5py.File(fname, "r")
    nr1 = f.attrs.get("nr1")
    nr2 = f.attrs.get("nr2")
    nr3 = f.attrs.get("nr3")
    charge = np.zeros((nr1,nr2,nr3))
    for i in range(0,nr3):   
        dset_label = "K"+str(i+1)   # numbered from 1 to nr3 in file hdf5
        tempcharge = np.array(f[dset_label])
        charge[:,:,i] = np.reshape(np.array(tempcharge),(nr1,nr2))
    
    return charge


def read_wavefunction_file_hdf5(fname):
    """
    Reads an hdf5 wavefunction file written with QE. Returns a dictionary with
    the data structure in the hdf5 file. 
    """
 
    import h5py
    
    f = h5py.File(fname, "r")    
    nkpoints = len(f["KPOINT1"].attrs.values())
    #print ("nkpoints = ",nkpoints)

    wavefunctions = {}

    for i in range(0,nkpoints):
        temp = {}
        kpoint_label = "KPOINT"+str(i+1)
        # read the attributes at each kpoint
        attrs_to_read = ["gamma_only", "igwx", "ik", "ispin","ngw","nk","nbnd","nspin","scale_factor"]
        for attr in attrs_to_read:
            temp[attr] = f[kpoint_label].attrs.get(attr)
        for iband in range(0,temp["nbnd"]):
            band_label = "BAND"+str(iband+1)
            temp[band_label] = np.array(f[kpoint_label][band_label])
        
        wavefunctions[kpoint_label] = temp
        
    return wavefunctions
    
    
################################################################################
# Reader of pseudopotential files and auxiliary functions.
################################################################################
# Warning: limited functionalities for now
#
def get_tag(line):
    """
    Check if the input string is an xml tag, i.e. it contains between "<" and ">" the "/" and any alphanumeric character.
    If so, returns the string between  "<" and ">". If "/" is present, it is in [0] position in the returned string.
    If not a tag, returns None
    """

    import re

    line = line.strip(" \n\t")         # first strip spaces, endline chars, tabs
    pat = re.compile(r'<\/?[\w\ =\+\-\.\"]+\/?>')    # a tag may contain between "<" and ">" the "/" and any alphanumeric character
    if pat.match(line):
        return line.strip(" <>")     # returns the tag without "<" and ">"

################################################################################
# Read tags in list_tags and returns a dictionary
#
def read_tags(lines,list_tags):
    """
    This function loops over the lines in input and returns a dictionary 
    with the content of each tag, but only if they are in list_tags
    """

    dic = {}
    content = ""
    i = 0
    add_content = False
    while (i<len(lines)):
        tag = get_tag(lines[i])
        if ( tag!=None): tag = tag.split()[0]
        if ((tag!=None) and (tag[0]!="/") and (tag  in list_tags)):
            #print ("Reading tag... ",tag)
            add_content = True
        elif ((tag!=None) and (tag[0]=="/") and (tag.strip("/") in list_tags)):
            tag = tag.strip("/")
            #print ("Closing tag... ",tag)
            dic[tag] = content
            content = ""
            add_content = False
        elif ( add_content):
            content += lines[i]
        i += 1
    return dic



def read_pseudo_file(fname):
    """
    This function reads a pseudopotential file in the QE UPF format (text), returning
    the content of each tag in a dictionary. 
    WARNING: does not handle multiple tags with the same name yet and has limited 
    functionalities for now. It is meant to be used only for postqe, not as a general
    reader of pseudopotentials files.
    """
    
    list_tags = ["PP_INFO","PP_HEADER","PP_MESH","PP_NLCC", "PP_LOCAL","PP_NONLOCAL","PP_PSWFC","PP_RHOATOM"]
    
    lines = []
    with open(fname, "r") as temp:
        for line in temp:
            lines.append(line)

    pseudo = read_tags(lines,list_tags)
    ### convert strings to float numpy arrays
    rloc = np.array( [ float(x) for x in pseudo["PP_LOCAL"].split()] )
    pseudo["PP_LOCAL"] = rloc
    #### Read subfields
    list_tags_PP_MESH = ["PP_R","PP_RAB"]
    pseudo["PP_MESH"] = read_tags(pseudo["PP_MESH"].splitlines(),list_tags_PP_MESH)
    rr =  np.array( [float(x) for x in pseudo["PP_MESH"]["PP_R"].split() ] )
    rrab= np.array ([ float (x) for x in pseudo["PP_MESH"]["PP_RAB"].split()  ] )
    tempdict = dict(PP_R=rr, PP_RAB=rrab )
    pseudo["PP_MESH"] = tempdict

    rhoat = np.array([ float(x) for x in pseudo["PP_RHOATOM"].split() ] )
    pseudo["PP_RHOATOM"] = rhoat
    
    list_tags_PP_NONLOCAL = ["PP_BETA","PP_DIJ"] 
    pseudo["PP_NONLOCAL"] = read_tags(pseudo["PP_NONLOCAL"].splitlines(),list_tags_PP_NONLOCAL)
        
    return pseudo


################################################################################
# Other readers, writers, auxiliary functions.
################################################################################
def write_charge(fname,charge,header):
    """
    Write the charge or another quantity calculated by postqe into a file fname.    
    """
    
    fout = open(fname, "w")
    
    fout.write(header)
    
    nr = charge.shape
    count = 0
    #for x in range(0,nr[0]):
    #    for y in range(0,nr[1]):
    #        for z in range(0,nr[2]):
    for z in range(0,nr[2]):
        for y in range(0,nr[1]):
            for x in range(0,nr[0]):
                fout.write("  {:.9E}".format(charge[x,y,z]))
                count += 1
                if (count%5==0):
                    fout.write("\n")
                        
    fout.close()
    
    
def create_header(prefix,nr,ibrav,celldms,nat,ntyp,atomic_species,atomic_positions):
    """
    Creates the header lines for the output file. A few fields are different from QE.
    """

    text = prefix+"\n"
    text += "{:8d} {:8d} {:8d} {:8d} {:8d} {:8d} {:8d} {:8d}\n".format(nr[0],nr[1],nr[2],nr[0],nr[1],nr[2],nat,ntyp)
    text += "{:6d}    {:8E}  {:8E}  {:8E}  {:8E}  {:8E}  {:8E}\n".format(ibrav,*celldms)
    text += "      "+4*"XXXX   "+"\n"
    
    ityp = 1
    for typ in atomic_species:
        text += "{:4d} ".format(ityp)+typ["name"]+"\n"
        ityp += 1

    ipos = 1
    for pos in atomic_positions:
        text += "{:4d}  ".format(ipos)
        for i in range(0,3):
            text += "{:9E}  ".format(pos["_text"][i])
        text += pos["name"]+"\n"
        ipos += 1
    
    return text
    

# A function only for testing for now...  
def read_pp_out_file(fname, skiplines, nr):
    """
    This function reads the output charge (or other quantity) as the output 
    format of QE pp. Only for testing... Initial lines are not processed
    and the function needs to know how many there are (skiplines).
    """
    
    tempcharge = []
    i=0           # initialize counters
    countline=1
    with open(fname, "r") as lines:
        for line in lines:
            linesplit=line.split()
            if countline>skiplines:                     # skip the first "skiplines" lines
                for j in range(0,len(linesplit)):       # len(linesplit)=5 except maybe for the last line
                    tempcharge.append(float(linesplit[j]))

            countline += 1
    
    
    charge = np.zeros((nr[0],nr[1],nr[2]))
    count = 0
    #for x in range(0,nr[0]):
    #    for y in range(0,nr[1]):
    #        for z in range(0,nr[2]):
    for z in range(0,nr[2]):
        for y in range(0,nr[1]):
            for x in range(0,nr[0]):
                charge[x,y,z] = tempcharge[count]
                count += 1

    return charge
    
    
def read_charge_text_file(fname,skiplines,nr1,nr2,nr3):
    """
    Reads the charge or another quantity calculated by postqe into a file fname.
    For testing...
    """
    
    tempcharge = []
    i=0           # initialize counters
    countline=1
    with open(fname, "r") as lines:
        for line in lines:
            linesplit=line.split()
            if countline>skiplines:                     # skip the first "skiplines" lines
                for j in range(0,len(linesplit)):       # len(linesplit)=5 except maybe for the last line
                    g2 = float(linesplit[j])
                    if g2<0.1:
                        tempcharge.append(1.0E16)
                    else:
                        tempcharge.append(g2)

            countline += 1
    
    temp2charge = np.array(tempcharge)
    charge = np.reshape(np.array(tempcharge),(nr1,nr2,nr3))
    return charge
    
    fout.close()
    
###########################################
#
# This is only for testing the functions in this module
if __name__ == "__main__":
    prefix = "../tests/"
    from readutils import read_pseudo_file
    pseudo = read_pseudo_file(prefix+"Al.pz-vbc.UPF")
 
    print ("PP_INFO\n")
    print (pseudo["PP_INFO"])
    print ("PP_MESH\n")
    print (pseudo["PP_MESH"])
    
    print (pseudo["PP_MESH"]["PP_R"])
    print (pseudo["PP_MESH"]["PP_RAB"])
    