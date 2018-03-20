# -*- coding: utf-8 -*-

####################################################################################
# Integron_Finder - Integron Finder aims at detecting integrons in DNA sequences   #
# by finding particular features of the integron:                                  #
#   - the attC sites                                                               #
#   - the integrase                                                                #
#   - and when possible attI site and promoters.                                   #
#                                                                                  #
# Authors: Jean Cury, Bertrand Neron, Eduardo PC Rocha                             #
# Copyright © 2015 - 2018  Institut Pasteur, Paris.                                #
# See the COPYRIGHT file for details                                               #
#                                                                                  #
# integron_finder is free software: you can redistribute it and/or modify          #
# it under the terms of the GNU General Public License as published by             #
# the Free Software Foundation, either version 3 of the License, or                #
# (at your option) any later version.                                              #
#                                                                                  #
# integron_finder is distributed in the hope that it will be useful,               #
# but WITHOUT ANY WARRANTY; without even the implied warranty of                   #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                    #
# GNU General Public License for more details.                                     #
#                                                                                  #
# You should have received a copy of the GNU General Public License                #
# along with this program (COPYING file).                                          #
# If not, see <http://www.gnu.org/licenses/>.                                      #
####################################################################################

import os
from tempfile import NamedTemporaryFile
try:
    from tests import IntegronTest
except ImportError as err:
    msg = "Cannot import integron_finder: {0!s}".format(err)
    raise ImportError(msg)

from integron_finder.topology import Topology
from integron_finder import utils


class TestUtils(IntegronTest):

    def test_read_single_dna_fasta(self):
        replicon_name = 'acba.007.p01.13'
        replicon_path = self.find_data(os.path.join('Replicons', replicon_name + '.fst'))
        replicon = utils.read_single_dna_fasta(replicon_path)
        self.assertEqual(replicon.id, 'ACBA.007.P01_13')
        self.assertEqual(replicon.name, replicon.name)
        self.assertEqual(len(replicon), 20301)
        self.assertTrue(replicon.seq.startswith('TGCTGCTTGGATGCCCGAGGCATAGACTGTACAAAAAAACAGTCATAACAAGCCATGAAA'))
        self.assertTrue(replicon.seq.endswith('CGACCCACGGCGTAACGCGCT'))

    def test_read_multi_prot_fasta(self):
        replicon_name = 'acba.007.p01.13'
        replicon_path = self.find_data(os.path.join('Proteins', replicon_name + '.prt'))
        replicon = utils.read_multi_prot_fasta(replicon_path)
        expected_seq_id = ['ACBA.007.P01_13_{}'.format(i) for i in range(1, 24)]
        received_seq_id = [seq.id for seq in replicon]
        self.assertListEqual(expected_seq_id, received_seq_id)

    def test_FastaIterator(self):
        file_name = 'multi_fasta'
        replicon_path = self.find_data(os.path.join('Replicons', file_name + '.fst'))
        topologies = Topology('lin')

        seq_db = utils.FastaIterator(replicon_path)
        seq_db.topologies = topologies

        expected_seq_id = sorted(['ACBA.007.P01_13', 'LIAN.001.C02_10', 'PSSU.001.C01_13'])
        received_seq_id = sorted([seq.id for seq in seq_db])
        self.assertListEqual(expected_seq_id, received_seq_id)
        self.assertEqual(len(seq_db), 3)

        expected_seq_name = expected_seq_id
        seq_db = utils.FastaIterator(replicon_path)
        seq_db.topologies = topologies
        received_seq_name = sorted([seq.name for seq in seq_db])
        self.assertListEqual(expected_seq_name, received_seq_name)

        replicon_name = 'foo'
        seq_db = utils.FastaIterator(replicon_path, replicon_name=replicon_name)
        seq_db.topologies = topologies
        expected_seq_name = set([replicon_name])
        received_seq_id = set([seq.name for seq in seq_db])
        self.assertSetEqual(expected_seq_name, received_seq_id)

        seq_db = utils.FastaIterator(replicon_path)
        received_seq_top = [seq.topology for seq in seq_db]
        expected_seq_top = ['lin', 'lin', 'lin']
        self.assertListEqual(expected_seq_top, received_seq_top)

        with NamedTemporaryFile(mode='w') as topology_file:
            topology_file.write("""ACBA.007.P01_13 linear
LIAN.001.C02_10 circular
PSSU.001.C01_13 linear
""")
            topology_file.flush()
            topologies = Topology('lin', topology_file=topology_file.name)
            seq_db = utils.FastaIterator(replicon_path)
            seq_db.topologies = topologies
            received_seq_top = sorted([seq.topology for seq in seq_db])
            expected_seq_top = sorted(['lin', 'circ', 'lin'])
            self.assertListEqual(expected_seq_top, received_seq_top)

        file_name = 'acba_short'
        replicon_path = self.find_data(os.path.join('Replicons', file_name + '.fst'))
        topologies = Topology('circ')
        seq_db = utils.FastaIterator(replicon_path)
        seq_db.topologies = topologies
        received_seq_top = [seq.topology for seq in seq_db]
        expected_seq_top = ['lin']
        self.assertListEqual(expected_seq_top, received_seq_top)

        file_name = 'replicon_bad_char'
        replicon_path = self.find_data(os.path.join('Replicons', file_name + '.fst'))
        seq_db = utils.FastaIterator(replicon_path)

        # 2 sequences are rejected so 2 message are produced (for seq 2 and 4)
        expected_warning = """sequence seq_(4|2) contains invalid characters, the sequence is skipped.
sequence seq_(2|4) contains invalid characters, the sequence is skipped."""
        with self.catch_log() as log:
            received_seq_id = sorted([seq.id for seq in seq_db if seq])
            got_warning = log.handlers[0].stream.getvalue().strip()
        self.assertRegexpMatches(got_warning, expected_warning)
        expected_seq_id = sorted(['seq_1', 'seq_3'])
        self.assertListEqual(expected_seq_id, received_seq_id)

        file_name = 'replicon_too_short'
        replicon_path = self.find_data(os.path.join('Replicons', file_name + '.fst'))
        seq_db = utils.FastaIterator(replicon_path)
        expected_warning = """sequence seq_(4|2) is too short \(32 bp\), the sequence is skipped \(must be > 50bp\).
sequence seq_(4|2) is too short \(32 bp\), the sequence is skipped \(must be > 50bp\)."""
        with self.catch_log() as log:
            received_seq_id = sorted([seq.id for seq in seq_db if seq])
            got_warning = log.handlers[0].stream.getvalue().strip()
        self.assertRegexpMatches(got_warning, expected_warning)
        expected_seq_id = sorted(['seq_1', 'seq_3'])
        self.assertListEqual(expected_seq_id, received_seq_id)

    def test_model_len(self):
        model_path = self.find_data(os.path.join('Models', 'attc_4.cm'))
        self.assertEqual(utils.model_len(model_path), 47)
        bad_path = 'nimportnaoik'
        with self.assertRaises(IOError) as ctx:
            with self.catch_log():
                utils.model_len(bad_path)
        self.assertEqual(str(ctx.exception),
                         "Path to model_attc '{}' does not exists".format(bad_path))
        bad_path = self.find_data(os.path.join('Models', 'phage-int.hmm'))
        with self.assertRaises(RuntimeError) as ctx:
            with self.catch_log():
                utils.model_len(bad_path)
        self.assertEqual(str(ctx.exception),
                         "CLEN not found in '{}', maybe it's not infernal model file".format(bad_path))


    def test_get_name_from_path(self):
        self.assertEqual(utils.get_name_from_path('/foo/bar.baz'), 'bar')
        self.assertEqual(utils.get_name_from_path('bar.baz'), 'bar')
        self.assertEqual(utils.get_name_from_path('../foo/bar.baz'), 'bar')
        self.assertEqual(utils.get_name_from_path('../foo/bar'), 'bar')


    def test_non_gembase_parser(self):
        desc = 'ACBA.007.P01_13_1 # 55 # 1014 # 1 # ID=1_1;partial=00;start_type=ATG;rbs_motif=None;' \
               'rbs_spacer=None;gc_cont=0.585'
        prot_attr = utils.non_gembase_parser(desc)

        expected = utils.SeqDesc('ACBA.007.P01_13_1', 1, 55, 1014)
        self.assertTupleEqual(expected, prot_attr)

    def test_gembase_parser(self):
        desc = 'OBAL001.B.00005.C001_00003 C ATG TAA 3317 4294 Valid AKN90_RS00015 978 ' \
               '@WP_053105352.1@ AKN90_RS00015 1 3317 4294 | alpha-L-glutamate ligase-like protein  (translation)'
        prot_attr = utils.gembase_parser(desc)

        expected = utils.SeqDesc('OBAL001.B.00005.C001_00003', -1, 3317, 4294)
        self.assertTupleEqual(expected, prot_attr)
