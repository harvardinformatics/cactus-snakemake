#############################################################################
# Functions to help parse trees in the cactus snakemake pipeline
#
# Gregg Thomas, April 2022
#############################################################################

import os
import re
import logging

from lib.cactuslib import spacedOut as SO

#############################################################################

cactuslib_logger = logging.getLogger('cactuslib')
# Get the logger for the cactuslib module

#############################################################################

def remBranchLength(treestring):
# Removes branch lengths from a tree.
	treestring = re.sub(r'[)][\d\w<>/.eE_:-]+', ')', treestring);
	treestring = re.sub(r':[\d.eE-]+', '', treestring);
	return treestring;
    
#############################################################################

def getDesc(d_spec, d_treedict):
# This function takes a species in the current tree and the dictionary of the current tree
# returned by treeparse and finds the direct descendants of the species.
	d_list = [];
	for node in d_treedict:
		if d_treedict[node][1] == d_spec:
			d_list.append(node);

	if d_list == []:
		return [d_spec];
	else:
		return d_list;

#############################################################################

def getClade(c_spec, c_treedict):
# This function takes a species in the current tree and the dictionary of the current tree
# returned by treeparse and finds all tip labels that are descendants of the current node.
# This is done by getting the direct descendants of the current node with getDesc and then
# recursively calling itself on those descendants.

	clade = [];
	c_desc = getDesc(c_spec, c_treedict);
	for d in c_desc:
		if c_treedict[d][2] != 'tip':
			clade.append(getClade(d, c_treedict));
		else:
			clade.append(d);

	r_clade = [];
	for c in clade:
		if type(c) == list:
			for cc in c:
				r_clade.append(cc);
		else:
			r_clade.append(c);

	return r_clade;

#############################################################################

def pathToNode(query_node, target_node, tree_dict):
# Gets all nodes between provided node and root of the tree
	path_to_node = [];
	while tree_dict[query_node][1] != target_node:
		path_to_node.append(tree_dict[query_node][1]);
		query_node = tree_dict[query_node][1];
	return path_to_node;

#############################################################################

def maxDistToTip(node, tree_dict):
# This function returns a list of the nodes between the current node and the root of the tree.

	if tree_dict[node][2] == 'tip':
		return 0;

	tips_to_check = getClade(node, tree_dict);
	max_dist = -1;
	for tip in tips_to_check:
		cur_dist = len(pathToNode(tip, node, tree_dict));
		if cur_dist > max_dist:
			max_dist = cur_dist;

	return max_dist;

#############################################################################
def treeParse(tree, debug=False):
# The treeParse function takes as input a rooted phylogenetic tree with branch lengths and returns the tree with node labels and a
# dictionary with usable info about the tree in the following format:
# node:[branch length (if present), ancestral node, node type, node label (if present)]

	tree = tree.strip();
	if tree[-1] != ";":
		tree += ";";
	# Some string handling

	nodes, bl, supports, ancs = {}, {}, {}, {};
	# Initialization of all the tracker dicts

	topology = remBranchLength(tree);

	if debug == 1:
		print("TOPOLOGY:", topology);

	##########

	nodes = {};
	for n in topology.replace("(","").replace(")","").replace(";","").split(","):
		nodes[n] = 'tip';
	# Retrieval of the tip labels

	if debug == 1:
		print("NODES:", nodes);

	##########

	new_tree = "";
	z = 0;
	numnodes = 1;
	while z < (len(tree)-1):
		new_tree += tree[z];
		if tree[z] == ")":
			node_label = "<" + str(numnodes) + ">";
			new_tree += node_label;
			nodes[node_label] = 'internal';
			numnodes += 1;
		z += 1;
	nodes[node_label] = 'root';
	rootnode = node_label;
	# This labels the original tree as new_tree and stores the nodes and their types in the nodes dict

	if debug:
		print("NEW TREE:", new_tree);
		print("TREE:", tree);
		print("NODES:", nodes);
		print("ROOTNODE:", rootnode);
	
	##########

	topo = "";
	z = 0;
	numnodes = 1;
	while z < (len(topology)-1):
		topo += topology[z];
		if topology[z] == ")":
			node_label = "<" + str(numnodes) + ">";
			topo += node_label;
			numnodes += 1;
		z += 1;
	# This labels the topology with the same internal labels

	if debug:
		print("TOPO:", topo);

	##########

	for node in nodes:
		if node + node in new_tree:
			new_tree = new_tree.replace(node + node, node);

	##########

	for node in nodes:
	# One loop through the nodes to retrieve all other info
		if debug:
			print("NODE:", node);

		if nodes[node] == 'tip':
			supports[node] = "NA";
			if node + ":" in tree:
				cur_bl = re.findall(node + r":[\d.Ee-]+", new_tree);
				cur_bl = cur_bl[0].replace(node + ":", "");
				if debug:
					print("FOUND BL:", cur_bl);
				bl[node] = cur_bl;				
			else:
				bl[node] = "NA";

		elif nodes[node] == 'internal':
			if node + node in new_tree:
				new_tree = new_tree.replace(node + node, node);

			if node + "(" in new_tree or node + "," in new_tree or node + ")" in new_tree:
				if debug:
					print("NO BL OR LABEL");
				supports[node] = "NA";
				bl[node] = "NA";

			elif node + ":" in new_tree:
				supports[node] = "NA";
				cur_bl = re.findall(node + r":[\d.Ee-]+", new_tree);
				cur_bl = cur_bl[0].replace(node + ":", "");
				if debug:
					print("FOUND BL:", cur_bl);
				bl[node] = cur_bl;								

			else:
				cur_bsl = re.findall(node + r"[\d\w<>_*+.Ee/-]+:[\d.Ee-]+", new_tree);
				if cur_bsl:
				# If the pattern above is found then the node has both support and branch length
					cur_bs = cur_bsl[0].replace(node, "");
					cur_bs = cur_bs[:cur_bs.index(":")];
					cur_bl = cur_bsl[0].replace(node, "").replace(cur_bs, "").replace(":", "");
					if debug:
						print("FOUND BL AND LABEL:", cur_bl, cur_bs);
					supports[node] = cur_bs;
					bl[node] = cur_bl;
					#new_tree = new_tree.replace(cur_bs, "");
				else:
				# If it is not found then the branch only has a label
					cur_bs = re.findall(node + r"[\w*+.<> -]+", new_tree);
					cur_bs = cur_bs[0].replace(node, "");
					if debug:
						print("FOUND LABEL:", cur_bs);
					supports[node] = cur_bs;
					bl[node] = "NA";
					#new_tree = new_tree.replace(cur_bs, "");

		elif nodes[node] == 'root':
			bl[node] = "NA";
			supports[node] = new_tree[new_tree.index(node)+len(node):];
			ancs[node] = "NA";
			continue;
		# Next we get the ancestral nodes. If the node is the root this is set to NA.

		##########

		anc_match = re.findall('[(),]' + node, new_tree);

		anc_match = re.findall(node, topo);
		if debug:
			print("ANC MATCH:", anc_match);

		##########

		anc_tree = new_tree[new_tree.index(anc_match[0]):][1:];
		# Ancestral labels are always to the right of the node label in the text of the tree, so we start our scan from the node label

		if debug:
			print("NODE:", node);
			print("ANC_MATCH:", anc_match);
			print("ANC_TREE:", anc_tree);

		##########
			
		cpar_count = 0;
		cpar_need = 1;

		for i in range(len(anc_tree)):
		# We find the ancestral label by finding the ) which matches the nesting of the number of ('s found
			if anc_tree[i] == "(":
				cpar_need = cpar_need + 1;
			if anc_tree[i] == ")" and cpar_need != cpar_count:
				cpar_count = cpar_count + 1;
			if anc_tree[i] == ")" and cpar_need == cpar_count:
				anc_tree = anc_tree[i+1:];
				ancs[node] = anc_tree[:anc_tree.index(">")+1];
				break;

		if debug:
			print("FOUND ANC:", ancs[node]);
			print("---");

		##########

	####################

	nofo = {};
	for node in nodes:
		nofo[node] = [bl[node], ancs[node], nodes[node], supports[node]];
	# Now we just restructure everything to the old format for legacy support

	if debug:
	# Debugging options to print things out
		print(("\ntree:\n" + tree + "\n"));
		print(("new_tree:\n" + new_tree + "\n"));
		print(("topology:\n" + topo + "\n"));
		print("nodes:");
		print(nodes);
		print()
		print("bl:");
		print(bl);
		print()
		print("supports:");
		print(supports);
		print()
		print("ancs:");
		print(ancs);
		print()
		print("-----------------------------------");
		print()
		print("nofo:");
		print(nofo);
		print()

	return nofo, topo, rootnode;

#############################################################################

def readTips(input_file, main, pad):
# This function reads the cactus input file and initializes the tips dictionary
    
    tips = {};
    # The main dictionary for storing information and file paths for tips in the tree:
    # [output fasta file from mask step] : { 'input' : "original genome fasta file", 'name' : "genome name in tree", 'output' : "expected output from mask step (same as key)" }

    first = True;
    for line in open(input_file):
        if not line.strip():
            continue;
        # Skip any blank lines

        if first:
            if main:
                cactuslib_logger.info(SO(f"User input tree", pad) + f"{line.strip()}");
            first = False;
            continue;
        # The first line contains the input tree... skip

        line = line.strip().split("\t");
        cur_base = os.path.basename(line[1]);
        tips[line[0]] = { 'input' : [line[1]], 'name' : line[0], 'output' : "NA" };
    ## Read the genome names and original genome fasta file paths from the same cactus input file used with cactus-prepare

    if cactuslib_logger.isEnabledFor(logging.DEBUG):
        cactuslib_logger.debug("TREE TIPS:");
        for g in tips:
            cactuslib_logger.debug(f"{g}: {tips[g]}")
        cactuslib_logger.debug("===================================================================================");
    ## Some output for debugging

    return tips;

#############################################################################

def initializeInternals(cactus_file, tips, main, pad):
# This function reads the cactus file generated by cactus-prepare and initializes the internals dictionary

    internals = {};
    # The main dictionary for storing information and file paths for internal nodes in the tree:
    # [node name] : { 'name' : "node name in tree", 'blast-inputs' : [the expected inputs for the blast step], 'align-inputs' : [the expected inputs for the align step],
    #                   'hal-inputs' : [the expected inputs for the hal2fasta step], 'blast-output' : "the .cigar file output from the blast step",
    #                   'align-output' : "the .hal file output from the align step", 'hal-output' : "the fasta file output from the hal2fasta step" }

    first = True;
    for line in open(cactus_file):
        if not line.strip():
            continue;
        # Skip any blank lines

        if first:
            anc_tree = line.strip();
            first = False;
            continue;
        # The first line contains the tree with internal nodes labeled... save this for later

        line = line.strip().split("\t");
        name = line[0];
        cur_base = os.path.basename(line[1]);

        if name in tips:
            tips[name]['output'] = cur_base;
        else:
            internals[name] = {  'name' : name, 
                                    'input-seqs' : "NA", 
                                    'hal-file' : cur_base.replace(".fa", ".hal"), 
                                    'cigar-file' : cur_base.replace(".fa", ".cigar"), 
                                    'seq-file' : cur_base };
    ## Read the internal node labels and output file paths from the file generated by cactus-prepare

    if main:
        cactuslib_logger.info(SO(f"Cactus labeled tree", pad) + f"{anc_tree}");

    return internals, anc_tree;

#############################################################################

def parseInternals(internals, tips, tinfo, anc_tree):
# This function parses the cactus tree with internal node labels and updates the internals dictionary 
# with the round and input sequences for each internal node

    internal_nodes = [ n for n in tinfo if tinfo[n][2] != 'tip' ];
    # Parse the tree with the internal node labels

    tip_list = list(tips.keys());

    ####################

    for node in internal_nodes:
        name = tinfo[node][3];
        # The cactus node label

        internals[name]['round'] = maxDistToTip(node, tinfo);
    ## One loop through the tree to get the round each node is in based on its maximum
    ## distance to a tip

    ####################

    for node in internal_nodes:
        name = tinfo[node][3];
        # Get the name of the current node

        expected_seq_inputs = [];
        # We will construct a list of all sequences required as input for this node -- all those
        # from nodes in the previous round

        cur_desc = getDesc(node, tinfo);
        # Get descendant nodes for the current node

        for tip in tips:
            expected_seq_inputs.append(tips[tip]['output']);

        if not all(tinfo[desc][2] == "tip" for desc in cur_desc):
            for node_check in internal_nodes:
                name_check = tinfo[node_check][3];
                #print(node, name, node_check, name_check)
                if internals[name]['round']-1 != internals[name_check]['round']:
                    continue;
                expected_seq_inputs.append(internals[name_check]['seq-file']);
                # Go through the internal nodes again and skip any that aren't in the previous round  

        internals[name]['input-seqs'] = expected_seq_inputs;
        # Add the expected input seqs to the main internals dict for this node       
    ## Another loop through the tree to get the input sequences for each node

    if cactuslib_logger.isEnabledFor(logging.DEBUG):
        cactuslib_logger.debug("TREE INTERNAL NODES:");
        for g in internals:
            cactuslib_logger.debug(f"{g}: {internals[g]}");
        cactuslib_logger.debug("===================================================================================");
        cactuslib_logger.debug("TREE TIPS:");
        for g in tips:
            cactuslib_logger.debug(f"{g}: {tips[g]}")
        cactuslib_logger.debug("===================================================================================");
    ## Some output for debugging

    return tips, internals;

#############################################################################