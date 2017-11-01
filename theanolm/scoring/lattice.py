#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A module that implements the Lattice class used by word lattice decoders.
"""

import logging

from theanolm.backend import InputError

class NodeNotFoundError(Exception):
    pass

class Lattice(object):
    """Word Lattice

    Word lattice describes a search space for decoding. The graph is represented
    as a list of nodes and links. Each node contains pointers to its incoming
    and outgoing links. Each link contains a pointer to the nodes in both ends.
    """

    class Link(object):
        """A link between two graph nodes.

        A link contains pointers to the start and end node. A node that has the
        link as an outgoing link can find the next node from ``end_node`` and a
        node that has the link as an incoming link can find the previous node
        from ``start_node``.
        """

        def __init__(self, start_node, end_node, word=None,
                     ac_logprob=None, lm_logprob=None, transitions=""):
            """Constructs a link.

            :type start_node: self.Node
            :param start_node: the node that has this link as an outgoing link

            :type end_node: self.Node
            :param end_node: the node that has this link as an incoming link

            :type word: str or int
            :param word: the word label on the link

            :type ac_logprob: float
            :param ac_logprob: acoustic log probability

            :type lm_logprob: float
            :param lm_logprob: language model log probability

            :type transitions: str
            :param transitions: transitions for an FST lattice
            """

            self.start_node = start_node
            self.end_node = end_node
            self.word = None
            self.ac_logprob = ac_logprob
            self.lm_logprob = lm_logprob
            self.transitions = transitions

    class Node(object):
        """A node in the graph.

        Outgoing and incoming links can be used to find the next and previous
        nodes in the topology.
        """

        def __init__(self, node_id):
            """Constructs a node with no links.

            :type node_id: int
            :param node_id: the ID that can be used to access the node in the
                            node list
            """

            self.id = node_id
            self.out_links = []
            self.in_links = []
            self.time = None
            self.best_logprob = None
            self.final = False

    def __init__(self):
        """Constructs an empty lattice.
        """

        self.nodes = []
        self.links = []
        self.initial_node = None
        self.utterance_id = None
        self.lm_scale = None
        self.wi_penalty = None

    def write_slf(self, output_file):
        """Writes the lattice in SLF format.

        :type output_file: file object
        :param output_file: a file where to write the output
        """

        output_file.write("VERSION=1.1\n")
        output_file.write('UTTERANCE="{}"\n'.format(self.utterance_id))
        fields = []
        if self.lm_scale is not None:
            fields.append("lmscale={}".format(self.lm_scale))
        if self.wi_penalty is not None:
            fields.append("wdpenalty={}".format(self.wi_penalty))
        if fields:
            output_file.write("\t".join(fields) + "\n")
        output_file.write("N={}\tL={}\n"
                          .format(len(self.nodes), len(self.links)))

        for node in self.nodes:
            fields = ["I={}".format(node.id)]
            if node.time is not None:
                fields.append("t={}".format(node.time))
            output_file.write("\t".join(fields) + "\n")

        for link_id, link in enumerate(self.links):
            fields = ["J={}".format(link_id),
                      "S={}".format(link.start_node.id),
                      "E={}".format(link.end_node.id)]
            if link.word is None:
                fields.append("W=!NULL")
            else:
                fields.append("W={}".format(link.word))
            if link.ac_logprob is not None:
                fields.append("a={}".format(link.ac_logprob + 0.0))
            if link.lm_logprob is not None:
                fields.append("l={}".format(link.lm_logprob + 0.0))
            output_file.write("\t".join(fields) + "\n")

    def write_kaldi(self, output_file, word_to_id):
        """Writes the lattice in Kaldi CompactLattice format.

        :type output_file: file object
        :param output_file: a file where to write the output

        :type word_to_id: Vocabulary
        :param word_to_id: mapping of words to Kaldi IDs
        """

        def write_normal_link(link):
            word = link.word
            if word is None:
                word = "<eps>"
            elif word == "</s>":
                word = "!SENT_END"
            output_file.write("{} {} {} {},{},{}\n".format(
                link.start_node.id,
                link.end_node.id,
                word_to_id[word],
                -link.lm_logprob + 0.0,
                -link.ac_logprob + 0.0,
                link.transitions))

        def write_final_link(link):
            output_file.write("{} {},{},{}\n".format(
                link.start_node.id,
                -link.lm_logprob + 0.0,
                -link.ac_logprob + 0.0,
                link.transitions))

        word_to_id['!SENT_END'] = 0

        output_file.write("{}\n".format(self.utterance_id))
        for node in self.nodes:
            for link in node.out_links:
                if link.end_node.final:
                    write_final_link(link)
                else:
                    write_normal_link(link)
        output_file.write("\n")

    def sorted_nodes(self):
        """Sorts nodes topologically, then by time.

        Returns a list which contains the nodes in sorted order. Uses the Kahn's
        algorithm to sort the nodes topologically, but always picks the node
        from the queue that has the lowest time stamp, if the nodes contain time
        stamps.
        """

        result = []
        # A queue of nodes to be visited next:
        node_queue = [self.initial_node]
        # The number of incoming links not traversed yet:
        in_degrees = [len(node.in_links) for node in self.nodes]
        while node_queue:
            node = node_queue.pop()
            result.append(node)
            for link in node.out_links:
                next_node = link.end_node
                in_degrees[next_node.id] -= 1
                if in_degrees[next_node.id] == 0:
                    node_queue.append(next_node)
                    node_queue.sort(key=lambda x: (x.time is None, x.time),
                                    reverse=True)
                elif in_degrees[next_node.id] < 0:
                    raise InputError("Word lattice contains a cycle.")

        if len(result) < len(self.nodes):
            logging.warning("Word lattice contains unreachable nodes.")
        else:
            assert len(result) == len(self.nodes)

        return result

    def _add_link(self, start_node, end_node):
        """Adds a link between two nodes.

        :type start_node: Node
        :param start_node: creates a link from this node

        :type end_node: Node
        :param end_node: creates a link to this node

        :rtype: Link
        :returns: the created link
        """

        link = self.Link(start_node, end_node)
        self.links.append(link)
        start_node.out_links.append(link)
        end_node.in_links.append(link)
        return link
