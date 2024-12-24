####################################################################################################################################################################
#   Filename:       StructuredProgramming_ajdc21.py
#   Summary:        Cascade circuit analyser using ABCD transformation matrices
#   Description:    This program takes a .net file as input which describes a cascade circuit, with <CIRCUIT>, <TERMS> and <OUTPUT> blocks. The program then finds the
#                   ABCD transformation matrix for each component in the circuit, and uses these to find the overall ABCD matrix for the circuit, at each frequency
#                   requested. The program then uses the ABCD matrices to find the input impedance, current, voltage and power, and output impedance, current, voltage
#                   and power, and current, voltage, and power gain at each frequency requested. The program then outputs these values to a .csv file.
#
#   Version:        1.0
#   Date:           01/5/2023
#   Author:         Alex Colvin
####################################################################################################################################################################


# ==== IMPORTS ======================================================================================================================================================
import numpy as np  # Matrix handling
import re  # Regular expressions
import csv  # CSV file handling
import sys  # Command line handling
import getopt  # Command line handling
import math
import os

# QUESTIONS: 1. How many test per function?
#            4. Pout and before outputs incorrect values for a_Tests

# === FUNCTIONS ====================================================================================================================================================


def splitFile(inputFile):
    """ Splits input .net file into its 3 sections: circuit, terms and output, and returns them as lists. 
    If a section is missing, an error is raised.

    :param inputFile: Input .net file name as a string
    :return: circuitInfo: List of strings containing circuit information from <CIRCUIT> block
    :return: termsInfo: List of strings containing terms information from <TERMS> block
    :return: outputInfo: List of strings containing output information from <OUTPUT> block

    >>> splitFile("./splitFileUTs/valid1.net")
    (['n1=1 n2=2 R=8.55\\n', 'n1=2 n2=0 R=141.9\\n'], ['VT=5 RS=50\\n', 'RL=75\\n', 'Fstart=10.0 Fend=10e+6 Nfreqs=10\\n'], [['Vin', 'V'], ['Vout', 'V']])

    >>> splitFile("./splitFileUTs/unorderedBlocks.net")
    (['n1=1 n2=2 R=8.55\\n', 'n1=2 n2=0 R=141.9\\n'], ['VT=5 RS=50\\n', 'RL=75\\n', 'Fstart=10.0 Fend=10e+6 Nfreqs=10\\n'], [['Vin', 'V'], ['Vout', 'V']])

    >>> splitFile("./splitFileUTs/missingBlock.net")
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot find <CIRCUIT> block

    >>> splitFile("./splitFileUTs/missspeltBlock.net")
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot find <CIRCUIT> block

    >>> splitFile("./splitFileUTs/Idontexist.net")
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot open file

    """

    # Define output lists
    circuitInfo = []
    termsInfo = []
    outputInfo = []

    # Read between header flags
    readCircuit = False
    readTerms = False
    readOutputs = False

    # Flags to check if all 3 headers are present
    circuitHeader = False
    termsHeader = False
    outputHeader = False

    # Open inputFile as read
    try:
        fp = open(inputFile, 'r')
    except:
        raise SystemExit("Error: Cannot open file")

    for line in fp:

        # Toggle flag false at end of block
        if line.strip() == "</CIRCUIT>":
            readCircuit = False
        if line.strip() == "</TERMS>":
            readTerms = False
        if line.strip() == "</OUTPUT>":
            readOutputs = False

        # Append words to output list if flag is true, and not a comment
        if readCircuit == True and line[0] != "#":
            circuitInfo.append(line)

        if readTerms == True and line[0] != "#":
            termsInfo.append(line)

        if readOutputs == True and line[0] != "#":
            outputInfo.append(line.split())

        # Toggle flag true at start of block
        if line.strip() == "<CIRCUIT>":
            readCircuit = True
            circuitHeader = True
        if line.strip() == "<TERMS>":
            readTerms = True
            termsHeader = True
        if line.strip() == "<OUTPUT>":
            readOutputs = True
            outputHeader = True

    # close file
    fp.close()

    # Check all 3 headers are present, raise an error if not
    if circuitHeader == False:
        raise SystemExit("Error: Cannot find <CIRCUIT> block")
    if termsHeader == False:

        raise SystemExit("Error: Cannot find <TERMS> block")
    if outputHeader == False:

        raise SystemExit("Error: Cannot find <OUTPUT> block")

    # Return output lists
    return circuitInfo, termsInfo, outputInfo


def formatCircuitInfo(circuitInfo):
    """ Formats circuit information from strings into a list of lists, each sub-list containing 
    node1, node2, component, and component value respectively. 
    If a component or node is missing, an error is raised.
    The function also reorders the sublists, such that the node pairs are in the order they would appear physically
    in the circuit.

    :param circuitInfo: List of strings containing circuit information from <CIRCUIT> block
    :return: circuitList: List of lists containing circuit information, each 
             sub-list containing node1, node2, component, and component value respectively

    >>> formatCircuitInfo(['n1=1 n2=2 R=8.55\\n', 'n1=2 n2=0 R=141.9\\n']) # General case
    [[1, 2, 'R', 8.55], [0, 2, 'R', 141.9]]

    >>> formatCircuitInfo(['n1=1 n2=2 C=3.18e-9\\n', 'n1=2 n2=0 L=1.59e-3\\n']) # General case 2
    [[1, 2, 'C', 3.18e-09], [0, 2, 'L', 0.00159]]

    >>> formatCircuitInfo([]) # Empty list
    Traceback (most recent call last):
    ...
    SystemExit: Error: No circuit information found in <CIRCUIT> block

    >>> formatCircuitInfo(['n1=1 R=8.55\\n', 'n1=2 n2=0 R=141.9\\n']) # Missing n2
    Traceback (most recent call last):
    ...
    SystemExit: Error: Missing n2 value in <CIRCUIT> block

    >>> formatCircuitInfo(['n1=2 n2=0 R=141.9\\n', 'n1=1 n2=2 R=8.55\\n']) # Unordered nodes
    [[1, 2, 'R', 8.55], [0, 2, 'R', 141.9]]

    >>> formatCircuitInfo(['n1=1 n2 =2 R = 8.55\\n', 'n1= 2 n2=0 R  =141.9\\n']) # Spaces around '='
    [[1, 2, 'R', 8.55], [0, 2, 'R', 141.9]]


    """

    # Define output list
    circuitList = []

    # Variables
    temp = []
    n1 = 0
    n2 = 0
    comp = ''
    val = 0.0

    # Check there is at least one line of circuit information
    if len(circuitInfo) < 1:
        raise SystemExit(
            "Error: No circuit information found in <CIRCUIT> block")

    # Iterate through each line in circuit
    for string in circuitInfo:
        # Flags to check n1, n2 and a component is present each line
        n1Flag = False
        n2Flag = False
        compFlag = False

        # Extracts: node 1 value, node 2 value, compenent type (R, L or C),
        # and component value respectively using regular expression (regex)

        if re.search(r"\bn1\s*=+\s*(\d+)\b", string):  # Search for 'n1='
            n1 = int(re.search(r"\bn1\s*=+\s*(\d+)\b", string).group(1))
            n1Flag = True

        if re.search(r"\bn2\s*=+\s*(\d+)\b", string):  # Search for 'n2='
            n2 = int(re.search(r"\bn2\s*=+\s*(\d+)\b", string).group(1))
            n2Flag = True

        # Search for component type and float value
        # Search for 'R='
        if re.search(r"\bR\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string):
            comp = 'R'
            val = float(
                re.search(r"\bR\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string).group(1))  # Retrieve value preceding '='
            compFlag = True

        # Search for 'L='
        if re.search(r"\bL\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string):
            comp = 'L'
            val = float(
                re.search(r"\bL\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string).group(1))
            compFlag = True

        # Search for 'C='
        if re.search(r"\bC\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string):
            comp = 'C'
            val = float(
                re.search(r"\bC\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string).group(1))
            compFlag = True

        # Search for 'G='
        if re.search(r"\bG\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string):
            comp = 'G'
            val = float(
                re.search(r"\bG\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", string).group(1))
            compFlag = True

        # Check all values are present, raise error otherwise
        if n1Flag == False:
            raise SystemExit("Error: Missing n1 value in <CIRCUIT> block")
        if n2Flag == False:
            raise SystemExit("Error: Missing n2 value in <CIRCUIT> block")
        if compFlag == False:
            raise SystemExit(
                "Error: Missing component type and/or value in <CIRCUIT> block")

        temp = [n1, n2, comp, val]  # Append values to temp list
        circuitList.append(temp)  # Append temp to circuit list

        # Sort circuitList in order of physical component occurence, from left to right
        for i in circuitList:
            i[:2] = sorted(i[:2])  # Sort the nodes so 0 is always n1
        # Sort from largest to smallest first element
        circuitList.sort(key=lambda x: x[0], reverse=True)
        # Then sort from smallest to largest second element
        circuitList.sort(key=lambda x: x[1])

    return circuitList


def formatTermsInfo(termsInfo):
    """Formats terms information from strings into 2 lists, the first list containing
    1. RS, VT,and RL, and 2. containg the range of frequencies respectively.
    Conductance (GS) is converted to resistance (RS) by taking the reciprocal.
    Norton current (IS) is converted to Thevenin voltage (VT) by multiplying by RS.
    If a value is missing, an error is raised.

    :param termsInfo: List of strings containing terms information from <TERMS> block
    :return: inOutList: List containing RS, VT, and RL respectively
    :return: freqList: List containing frequencies from freqStart to freqEnd in steps of freqStep

    >>> formatTermsInfo(['RS=50 VT=5\\n', 'RL=75\\n', 'Fstart=10.0 Fend=10e+6 Nfreqs=4\\n']) # General case
    ([5.0, 50.0, 75.0], array([1.00000e+01, 3.33334e+06, 6.66667e+06, 1.00000e+07]))

    >>> formatTermsInfo(['GS=0.02 IN=0.1\\n', 'RL=75\\n', 'Fstart=10.0 Fend=10e+6 Nfreqs=4\\n']) # General case 2
    ([5.0, 50.0, 75.0], array([1.00000e+01, 3.33334e+06, 6.66667e+06, 1.00000e+07]))

    >>> formatTermsInfo([]) # Empty list
    Traceback (most recent call last):
    ...
    SystemExit: Error: Missing RS, VT, RL, and/or frequency values in <TERMS> block

    >>> formatTermsInfo(['RS=50 VT=5\\n', 'RL=75\\n', 'Fend=10e+6 Nfreqs=4\\n']) # Missing Fstart
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot find start frequency (Fstart) in <TERMS> block

    >>> formatTermsInfo(['VT=5\\n', 'RL=75\\n', 'Fstart=10.0 Fend=10e+6 Nfreqs=4\\n']) # Missing RS=
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot find input resistance/conductance in <TERMS> block

    >>> formatTermsInfo(['RS=50 VT= 5\\n', 'RL=75\\n', 'Fstart = 10.0 Fend=10e+6 Nfreqs= 4\\n']) # Spaces around '='
    ([5.0, 50.0, 75.0], array([1.00000e+01, 3.33334e+06, 6.66667e+06, 1.00000e+07]))
    """

    # Define output list
    inOutList = []
    freqList = []

    # Variables
    RS = 0.0  # Input Resistance
    VT = 0.0  # Thevenin Voltage
    RL = 0.0  # Load Resistance

    # Check RS, RL and Freq string all present
    if len(termsInfo) < 3:
        raise SystemExit(
            "Error: Missing RS, VT, RL, and/or frequency values in <TERMS> block")

    # Search for RS= or GS=, allowing for spaces around =
    # Search for 'RS='
    if re.search(r"\bRS\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]):
        RS = float(re.search(
            r"\bRS\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]).group(1))  # Retrieve the float preceding '='

    # Search for 'GS='
    elif re.search(r"\bGS\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]):
        RS = 1 / \
            float(re.search(
                r"\bGS\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]).group(1))  # Retrieve the float preceding '='
    else:
        raise SystemExit(
            "Error: Cannot find input resistance/conductance in <TERMS> block")  # Raise error if neither RS or GS found

    # Search for VT= or IN=, allowing for spaces around =
    # Search for 'VT='
    if re.search(r"\bVT\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]):
        VT = float(re.search(
            r"\bVT\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]).group(1))  # Retrieve the float preceding '='

    # Search for 'IN='
    elif re.search(r"\bIN\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]):
        VT = float(re.search(
            r"\bIN\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[0]).group(1)) * RS  # Retrieve the float preceding '=' and convert to VT
    else:
        raise SystemExit(
            "Error: Cannot find source voltage or current in <TERMS> block")  # Raise error if neither VT or IN found

    # Search for RL=
    if re.search(r"\bRL\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[1]):
        RL = float(re.search(
            r"\bRL\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[1]).group(1))
    else:
        raise SystemExit("Error: Cannot find load resistance in <TERMS> block")

    # Outputs
    inOutList = [VT, RS, RL]

    # Search for Fstart=, Fend=, Nfreqs=, allowing for spaces around =
    # Search for 'Fstart='
    if re.search(r"\bFstart\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]):
        Fstart = float(re.search(
            r"\bFstart\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]).group(1))
    else:
        raise SystemExit(
            "Error: Cannot find start frequency (Fstart) in <TERMS> block")
    # Search for 'Fend='
    if re.search(r"\bFend\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]):
        Fend = float(re.search(
            r"\bFend\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]).group(1))
    else:
        raise SystemExit(
            "Error: Cannot find end frequency (Fend) in <TERMS> block")
    # Search for 'Nfreqs='
    if re.search(r"\bNfreqs\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]):
        Nfreqs = int(re.search(
            r"\bNfreqs\s*=+\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b", termsInfo[2]).group(1))
    else:
        raise SystemExit(
            "Error: Cannot find number of frequencies (Nfreqs) in <TERMS> block")

    # Create list of equally spaced frequencies
    freqList = np.linspace(Fstart, Fend, Nfreqs)

    return inOutList, freqList


def formatOutputInfo(outputInfo):
    """Takes the output information from the <OUTPUT> block and formats it into a list of real and imaginary 
    outputs and units, to be added as the top 2 rows of the output CSV file.
    If the unit is not specified, it defaults to L 
    If there are no outputs specified, an error is raised.

    :param outputInfo: List of strings containing the output information from the <OUTPUT> block
    :return outputs: List of strings containing the real and imaginary outputs
    :return units: List of strings containing the units of the real and imaginary outputs

    >>> formatOutputInfo([['Vin', 'V'], ['Vout', 'V']]) # General case
    (['Re(Vin)', 'Im(Vin)', 'Re(Vout)', 'Im(Vout)'], ['V', 'V', 'V', 'V'])

    >>> formatOutputInfo([['Vin', 'V'], ['Vout', 'V'], ['Av'], ['Ai']]) # General case 2
    (['Re(Vin)', 'Im(Vin)', 'Re(Vout)', 'Im(Vout)', 'Re(Av)', 'Im(Av)', 'Re(Ai)', 'Im(Ai)'], ['V', 'V', 'V', 'V', 'L', 'L', 'L', 'L'])

    >>> formatOutputInfo([]) # Empty list
    Traceback (most recent call last):
    ...
    SystemExit: Error: No output information found in <OUTPUT> block

    """

    outputs = []
    units = []

    # Check at least one output
    if len(outputInfo) < 1:
        raise SystemExit(
            "Error: No output information found in <OUTPUT> block")

    for i in outputInfo:
        outputs.append('Re('+i[0]+')')  # Create real part of output eg Re(Vin)
        # Create imaginary part of output eg Im(Vin)
        outputs.append('Im('+i[0]+')')

        if len(i) == 2:  # Double each unit to match real and imaginary parts
            units.append(i[1])
            units.append(i[1])
        else:  # If no unit specified, default to L
            units.append('L')
            units.append('L')

    return outputs, units


def findImpedance(circuitList, freqList):
    """Takes the circuit information from the <CIRCUIT> block and the frequency list and calculates the impedance 
    of each component, depending on its type. The impedance is then added to a list of impedances for each frequency.
    If an incorrect component is specified, an error is raised.
    If two components are specified between the same two nodes, an error is raised.

    :param circuitList: List of lists containing the circuit information from the <CIRCUIT> block
    :param freqList: List of floats containing the frequencies to calculate the impedance at
    :return impedanceList: List of lists containing the impedance of each component at each frequency

    >>> findImpedance([[1, 2, 'R', 8.55], [0, 2, 'R', 141.9]], [10, 20, 30]) # General case
    [[[1, 2, 8.55], [0, 2, 141.9]], [[1, 2, 8.55], [0, 2, 141.9]], [[1, 2, 8.55], [0, 2, 141.9]]]

    >>> findImpedance([[1, 2, 'C', 3.18e-9], [0, 2, 'L', 1.59e-3]], [10, 20, 30]) # General case 2
    [[[1, 2, -5004872.424273438j], [0, 2, 0.09990264638415543j]], [[1, 2, -2502436.212136719j], [0, 2, 0.19980529276831085j]], [[1, 2, -1668290.8080911462j], [0, 2, 0.29970793915246624j]]]

    >>> findImpedance([[1, 2, 'K', 8.55], [0, 2, 'R', 141.9]], [10, 20, 30]) # Invalid component type
    Traceback (most recent call last):
    ...
    SystemExit: Invalid Component Type: K

    >>> findImpedance([[1, 2, 'R', 8.55], [1, 2, 'R', 141.9]], [10, 20, 30]) # Two components between same nodes
    Traceback (most recent call last):
    ...
    SystemExit: Invalid Circuit: Invalid cascade circuit


    >>> findImpedance([[1, 2, 'R', 8.55], [1, 5, 'R', 141.9]], [10, 20, 30]) # Series components between non-adjacent nodes
    Traceback (most recent call last):
    ...
    SystemExit: Invalid Circuit: Invalid cascade circuit


    """
    # Outputs
    impedanceList = []

    # Variables
    temp = [0, 0, 0.0]  # [node1, node2, impedance]
    tempList = []
    nodeList = []

    for freq in freqList:

        tempList = []
        nodeList = []
        for circInfo in circuitList:

            match circInfo[2]:
                case 'R':
                    imp = circInfo[3]  # Impedance of resistor
                case 'G':
                    imp = 1/circInfo[3]  # Impedance of conductance
                case 'L':
                    imp = 2*np.pi*freq*circInfo[3]*1j  # Impedance of inductor
                case 'C':
                    # Impedance of capacitor
                    imp = 1/(2*np.pi*freq*circInfo[3]*1j)
                case _:  # Throw error if invalid component type
                    raise SystemExit("Invalid Component Type: "+circInfo[2])

            # Create Impedance List
            if (circInfo[0:2] not in nodeList and circInfo[1]-circInfo[0] == 1) or circInfo[0] == 0:
                temp[0:2] = circInfo[0:2]  # Node 1 and Node 2
                temp[2] = imp  # Append impedance to third element
                # Append node 1 and node 2 to nodeList
                nodeList.append(circInfo[0:2])
                tempList.append(temp.copy())
            else:  # Throw error if two series components between same node
                raise SystemExit(
                    "Invalid Circuit: Invalid cascade circuit")

        impedanceList.append(tempList.copy())

    return impedanceList


def shuntOrSeries(impedanceList):
    """Takes the impedance list and determines whether each component is a shunt or series component
    depending on whether node 1 is 0 or not. The impedance list is then updated to include this information.

    :param impedanceList: List of lists containing the impedance of each component at each frequency
    :return impedanceShuntSeries: List of lists containing the a boolean indicating shunt or series and
    the impedance of each component at each frequency,

    >>> shuntOrSeries([[[1, 2, 8.55], [0, 2, 141.9]], [[1, 2, 8.55], [0, 2, 141.9]]]) # General case
    [[[1, 8.55], [0, 141.9]], [[1, 8.55], [0, 141.9]]]

    >>> shuntOrSeries([[[1, 2, -5004872.424273438j], [0, 2, 0.09990264638415543j]], [[1, 2, -2502436.212136719j], [0, 2, 0.19980529276831085j]]]) # General case 2
    [[[1, (-0-5004872.424273438j)], [0, 0.09990264638415543j]], [[1, (-0-2502436.212136719j)], [0, 0.19980529276831085j]]]

    >>> shuntOrSeries([[[1, 2, 8.55], [0, 2, 141.9]], [[0, 2, 8.55], [0, 2, 141.9]]]) # Two components between same node
    [[[1, 8.55], [0, 141.9]], [[0, 8.55], [0, 141.9]]]

    """

    impedanceShuntSeries = []

    temp = [0, 0.0]  # [shunt/series (0/1), impedance]
    tempList = []

    for i in impedanceList:

        tempList = []
        for j in i:
            if j[0] == 0:  # If n1 is 0, then it is a shunt component
                temp[0] = 0
            else:  # If node 1 is not 0, then it is a series component
                temp[0] = 1

            temp[1] = j[2]  # Append Impedance (stays the same)

            tempList.append(temp.copy())

        impedanceShuntSeries.append(tempList.copy())

    return impedanceShuntSeries


def createABCDmat(impedanceShuntSeries):
    """Takes the impedanceShuntSeries list and creates the ABCD matrix for each frequency, by multiplying
    the ABCD matrices of each individual component together. The ABCD matrices are then added to a list of ABCD matrices

    :param impedanceShuntSeries: List of lists containing the a boolean indicating shunt or series and
    the impedance of each component at each frequency
    :return ABCDmatrices: List of matrices containing the ABCD matrix for each frequency

    >>> createABCDmat([[[0, 8.55], [1, 141.9]], [[0, 8.55], [1, 141.9]]]) # General case
    [array([[1.00000000e+00+0.j, 1.41900000e+02+0.j],
           [1.16959064e-01+0.j, 1.75964912e+01+0.j]]), array([[1.00000000e+00+0.j, 1.41900000e+02+0.j],
           [1.16959064e-01+0.j, 1.75964912e+01+0.j]])]

    >>> createABCDmat([[[0, (-0-5004872.424273438j)], [0, 0.09990264638415543j]], [[0, (-0-2502436.212136719j)], [0, 0.19980529276831085j]]]) # General case 2
    [array([[1. +0.j        , 0. +0.j        ],
           [0.-10.00974465j, 1. +0.j        ]]), array([[1.+0.j        , 0.+0.j        ],
           [0.-5.00487202j, 1.+0.j        ]])]

    >>> createABCDmat([[[1, 8.55], [0, 0]], [[1, 8.55], [0, 0]]]) # Divide by 0 error
    Traceback (most recent call last):
    ...
    SystemExit: Error: Divide by 0 error - check all components have non-zero values

    """
    # Create ABCD matrix for each frequency

    # Output
    ABCDmatrices = []
    # Variables
    ABCDnode = np.zeros((2, 2), dtype='complex128')  # 2x2 matrix for each node
    ABCDmat = np.identity(2, dtype='complex128')  # 2x2 Identity matrix

    for i in impedanceShuntSeries:
        ABCDmat = np.identity(2, dtype='complex128')  # 2x2 Identity matrix
        for j in i:
            # Series component
            if j[0] == 1:
                ABCDnode[0][0] = 1
                ABCDnode[0][1] = j[1]  # impedance
                ABCDnode[1][0] = 0
                ABCDnode[1][1] = 1
            # Shunt component
            else:
                ABCDnode[0][0] = 1
                ABCDnode[0][1] = 0
                if j[1] == 0:
                    raise SystemExit(
                        "Error: Divide by 0 error - check all components have non-zero values")
                else:
                    ABCDnode[1][0] = 1/j[1]  # 1/impedance (conductance)
                ABCDnode[1][1] = 1

            # Iteratively multiply ABCD matrix by ABCDnode matrix to create matrix for whole cascade circuit
            ABCDmat = ABCDmat@ABCDnode

        ABCDmatrices.append(ABCDmat.copy())

    return ABCDmatrices


def analyseCircuit(inOutList, ABCDmatrices, outputInfo):
    """Takes the ABCD matrices for each frequency, the input and output resistance, and the Thevenin voltage and calculates 
    the input voltage, current, power and impedance, output voltage, current, power and impedance, voltage gain, and current gain.
    Outputs the results requested in the <OUPTUT> section of the input file, for each frequency.
    Raises an error if an invalid output is requested.

    :param inOutList: List containing the Thevenin voltage and input and output resistance
    :param ABCDmatrices: List of matrices containing the ABCD matrix for each frequency
    :param outputInfo: List of strings containing the requested outputs
    :return circuitOutputs: List of lists containing the requested outputs for each frequency

    >>> analyseCircuit([5.0, 50.0, 75.0], [[[1.00000000e+00+0.j, 1.41900000e+02+0.j],\
              [1.16959064e-01+0.j, 1.75964912e+01+0.j]], [[1.00000000e+00+0.j, 1.41900000e+02+0.j],\
                [1.16959064e-01+0.j, 1.75964912e+01+0.j]]], [['Vin', 'V'], ['Vout', 'V'], ['Av'], ['Ai']])
    [[(0.7063669191534891+0j), (0.24424858891891116+0j), (0.3457814661134163+0j), (0.037924151772303696+0j)], [(0.7063669191534891+0j),\
 (0.24424858891891116+0j), (0.3457814661134163+0j), (0.037924151772303696+0j)]]

    >>> analyseCircuit([5.0, 50.0, 75.0], [[[1.0, 5.0],[1.0, 5.0]]], [['Vin', 'V'], ['Vout', 'V'], ['Av'], ['Ai']]) # Singular matrix
    [[0.09803921568627451, 0.0, 0.9375, 0.0125]]

    >>> analyseCircuit([5.0, 50.0, 75.0], [[[1.0, 5.0],[1.0, 6.0]]], [['Vdown', 'V'], ['Vup', 'V']]) # Invalid output
    Traceback (most recent call last):
    ...
    SystemExit: Invalid Output: Vdown


    """

    circuitOutputs = []

    VT = inOutList[0]
    ZS = inOutList[1]
    ZL = inOutList[2]

    # Calculate input voltage, current, power and impedance, output voltage, current, power and impedance, voltage gain, and current gain.
    for matrix in ABCDmatrices:

        # print(matrix)

        # Set A, B, C, D to values from ABCD matrix
        A = matrix[0][0]
        B = matrix[0][1]
        C = matrix[1][0]
        D = matrix[1][1]

        # Equations for output
        Vgain = (ZL)/(A*ZL+B)
        Igain = 1/(C*ZL+D)
        Pgain = Vgain*np.conj(Igain)

        Zin = (A*ZL+B)/(C*ZL+D)
        Zout = (D*ZS+B)/(C*ZS+A)

        Iin = VT/(ZS+Zin)
        Vin = Iin*Zin
        Pin = Vin*np.conj(Iin)

        if (A*D)-(B*C) == 0:  # Prevent division by 0
            Vout = 0.0
            Iout = 0.0
        else:
            Vout = ((D*Vin)-(B*Iin))/((A*D)-(B*C))
            Iout = ((A*Iin)-(C*Vin))/((A*D)-(B*C))

        Pout = Pin*Pgain

        # Append values to circuitOutputs in order of outputInfo
        temp = []
        for output in outputInfo:

            match output[0]:
                case 'Vin':
                    temp.append(Vin)
                case 'Vout':
                    temp.append(Vout)
                case 'Iin':
                    temp.append(Iin)
                case 'Iout':
                    temp.append(Iout)
                case 'Pin':
                    temp.append(Pin)
                case 'Zout':
                    temp.append(Zout)
                case 'Pout':
                    temp.append(Pout)
                case 'Zin':
                    temp.append(Zin)
                case 'Ai':
                    temp.append(Igain)
                case 'Av':
                    temp.append(Vgain)
                case _:  # If output is not valid, throw error
                    raise SystemExit("Invalid Output: " + output[0])

        circuitOutputs.append(temp.copy())

    return circuitOutputs


def generateOutputFile(circuitOutputs, outputInfo, freqList, outputFile):
    """ Takes the circuitOutputs list, the outputInfo list, the list of frequencies, and the name of the output file and
    creates a CSV file called outputFile.csv containing the requested outputs for each frequency. The outputs are split into their real and imaginary
    components and are outputted in separate columns. The first column is 10 characters wide and contains the frequency. The remaining columns are 11 characters wide
    All values are rounded to 3 decimal places.

    :param circuitOutputs: List of lists containing the requested outputs for each frequency
    :param outputInfo: List of strings containing the requested outputs
    :param freqList: List of frequencies
    :param outputFile: Name of output csv file as a string

    >>> generateOutputFile([[(0.7063669191534891+0j)]],[['Vin', 'V']], [10.0, 20.0, 30.0], ['']) # Missing outputFile
    Traceback (most recent call last):
    ...
    SystemExit: Error: Cannot create output file

    """

    circuitOutputsRI = []  # Circuit outputs split into real and imaginary components
    colWidth = 11  # Width of each column
    temp = []
    vals = []

    # Split outputInfo into outputs and units for first 2 rows
    [outputs, units] = formatOutputInfo(outputInfo)

    # Row 1:
    outputs = [word.rjust(colWidth)
               for word in outputs]  # Align commas of column
    # Add Freq to left column of outputs
    outputs = ['Freq'.rjust(colWidth-1)] + outputs

    # Row 2:
    units = [word.rjust(colWidth) for word in units]  # Align commas of column
    units = ['Hz'.rjust(colWidth-1)] + units  # Add Hz to left column

    # Row 3 onwards:
    # Split circuitOutputs into real and imaginary components, convert to string, and format to 3dp
    for list in circuitOutputs:
        temp = []
        for i in list:
            real = f"{i.real:.3e}"
            imag = f"{i.imag:.3e}"
            temp.append(str(real))
            temp.append(str(imag))
        circuitOutputsRI.append(temp.copy())

    # Convert freqList to string and format to 3dp
    strFreqList = [str(f"{i.real:.3e}") for i in freqList]

    for i, j in zip(circuitOutputsRI, strFreqList):
        # print(valRow)
        valRow = i.copy()
        valRow = [word.rjust(colWidth)
                  for word in valRow]  # Align commas of column
        # Append freq value to left column for each row of values
        valRow = [j.rjust(colWidth-1)] + valRow
        # print(valRow)
        vals.append(valRow.copy())
    
    
    # Create CSV file
    try:
        with open(outputFile, 'w+') as csvfile:  # Open CSV file with file name outputFile

            filewriter = csv.writer(csvfile)

            # Write first two rows
            filewriter.writerow(outputs)
            filewriter.writerow(units)

            # Write remaining rows
            for i in vals:
                filewriter.writerow(i + [''])
    except:
        raise SystemExit("Error: Cannot create output file")


    return


def main(inputCSV, outputNet):
    """ Takes the name of the input CSV file and the name of the output CSV file and calls the functions to split the input file,
    calculates the ABCD matrix for the circuit at each frequency, calculates the requested outputs, and generates the output CSV file.

    :param inputCSV: Name of input .net file as a string
    :param outputNet: Name of output CSV file as a string

    """

    try:
        with open(outputNet, 'w+') as csvfile:  # Open empty CSV file in case of error
            filewriter = csv.writer(csvfile)
    except:
        raise SystemExit("Error: Cannot create output file")

    [circuitStrings, termsStrings, outputStrings] = splitFile(inputCSV)
    print("----SPLIT FILE----")
    print(circuitStrings)
    print("\n")
    print(termsStrings)
    print("\n")
    print(outputStrings)
    print("\n\n")

    circuitFormatted = formatCircuitInfo(circuitStrings)
    print("----FORMAT CIRCUIT INFO----")
    print(circuitFormatted)
    print("\n\n")

    [inOutList, freqList] = formatTermsInfo(termsStrings)
    print("----FORMAT TERMS INFO----")
    print(inOutList)
    print("\n")
    print(freqList)
    print("\n\n")

    impedanceList = findImpedance(circuitFormatted, freqList)
    print("----FIND IMPEDANCE----")
    print(impedanceList)
    print("\n\n")

    shuntSeriesList = shuntOrSeries(impedanceList)
    print("----SHUNT OR SERIES----")
    print(shuntSeriesList)
    print("\n\n")

    ABCDmats = createABCDmat(shuntSeriesList)
    print("----CREATE ABCD MATRICES----")
    for i in ABCDmats:
        print(i)
        print("\n")
    print("\n\n")

    circuitOutputs = analyseCircuit(inOutList, ABCDmats, outputStrings)
    print("----ANALYSE CIRCUIT----")
    for i in circuitOutputs:
        print(i)
        print("\n")
    print("\n\n")

    generateOutputFile(circuitOutputs, outputStrings, freqList, outputFile)


    return


# === MAIN =======================================================================================================================================================


try:
    # Get command line arguments
    opts, args = getopt.getopt(sys.argv[1:], "", [])
    if len(args) < 2:  # If there are not enough command line arguments, throw error
        print("Usage: python my_program.py <input_file_name.net> <output_file_name.csv>")
    else:
        inputFile = args[0]  # Get input file name
        outputFile = args[1]  # Get output file name
except getopt.GetoptError as err:  # If command line arguments are invalid, throw error
    print(err)
    print("Usage: python my_program.py <input_file_name.net> <output_file_name.csv>")


main(inputFile, outputFile)  # Call main function

# if __name__ == '__main__':
#     import doctest
#     doctest.testmod()
