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
import colorlog
from subprocess import call

import numpy as np
import pandas as pd

from .infernal import local_max, expand

_log = colorlog.getLogger(__name__)


def search_attc(attc_df, keep_palindromes, dist_threshold, replicon_size):
    """
    Parse the attc data set (sorted along start site) for the given replicon and return list of arrays.
    One array is composed of attC sites on the same strand and separated by a distance less than 5kb.

    :param attc_df:
    :type attc_df: :class:`pandas.DataFrame`
    :param bool keep_palindromes: True if the palindromes must be kept in attc result, False otherwise
    :param int dist_threshold: the maximal distance between 2 elements to aggregate them
    :param int replicon_size: the replicon number of base pair
    :return: a list attC sites found on replicon
    :rtype: list of :class:`pandas.DataFrame` objects
    """
    ok = False

    position_bkp_minus = []
    position_bkp_plus = []

    attc_plus = attc_df[attc_df.sens == "+"].copy()
    attc_minus = attc_df[attc_df.sens == "-"].copy()

    if not keep_palindromes:
        attc_df = attc_df.sort_values(["pos_beg", "evalue"]).drop_duplicates(subset=["pos_beg"]).copy()
        attc_plus = attc_df[attc_df.sens == "+"].copy()
        attc_minus = attc_df[attc_df.sens == "-"].copy()

    # can be reordered
    if (attc_plus.pos_beg.diff() > dist_threshold).any() or (attc_minus.pos_beg.diff() > dist_threshold).any():
        if not attc_plus.empty:
            bkp_plus = attc_plus[attc_plus.pos_beg.diff() > dist_threshold].index
            position_bkp_plus = [attc_plus.index.get_loc(i) for i in bkp_plus]
        if not attc_minus.empty:
            bkp_minus = attc_minus[(attc_minus.pos_beg.diff() > dist_threshold)].index
            position_bkp_minus = [attc_minus.index.get_loc(i) for i in bkp_minus]
        ok = True
    if not attc_plus.empty and not attc_minus.empty:
        ok = True

    if not ok:
        if attc_df.empty:
            attc_array = []
        else:
            attc_array = [attc_df]
    else:
        if attc_plus.empty:
            array_plus = []
        else:
            array_plus = np.split(attc_plus.values, position_bkp_plus)
            # array_plus is a list of np.array
            first_pos_beg = array_plus[0][0][4]
            last_pos_beg = array_plus[-1][-1][4]
            if len(array_plus) > 1 and (first_pos_beg - last_pos_beg) % replicon_size < dist_threshold:
                array_plus[0] = np.concatenate((array_plus[-1], array_plus[0]))
                del array_plus[-1]

        if attc_minus.empty:
            array_minus = []
        else:
            array_minus = np.split(attc_minus.values, position_bkp_minus)
            # array_minus is a list of np.array
            first_pos_beg = array_minus[0][0][4]
            last_pos_beg = array_minus[-1][-1][4]
            if len(array_minus) > 1 and (first_pos_beg - last_pos_beg) % replicon_size < dist_threshold:
                array_minus[0] = np.concatenate((array_minus[-1], array_minus[0]))
                del array_minus[-1]

        tmp = array_plus + array_minus

        attc_array = [pd.DataFrame(i, columns=["Accession_number", "cm_attC", "cm_debut",
                                               "cm_fin", "pos_beg", "pos_end", "sens", "evalue"]) for i in tmp]
        # convert positions to int, and evalue to float
        intcols = ["cm_debut", "cm_fin", "pos_beg", "pos_end"]
        for a in attc_array:
            a[intcols] = a[intcols].astype(int)
            a["evalue"] = a["evalue"].astype(float)
    return attc_array


def find_attc(replicon_path, replicon_id, cmsearch_path, out_dir, model_attc, cpu=1):
    """
    Call cmsearch to find attC sites in a single replicon.

    :param str replicon_path: the path of the fasta file representing the replicon to analyse
    :param str replicon_id: the id of the replicon to analyse
    :param str cmsearch_path: the path to the cmsearch executable
    :param str out_dir: the path to the directory where cmsearch outputs will be stored
    :param str model_attc: path to the attc model (Covariance Matrix)
    :param int cpu: the number of cpu used by cmsearch
    :returns: None, the results are written on the disk
    :raises RuntimeError: when cmsearch run failed
    """
    cmsearch_cmd = [cmsearch_path,
                    "--cpu", str(cpu),
                    "-o", os.path.join(out_dir, replicon_id + "_attc.res"),
                    "--tblout", os.path.join(out_dir, replicon_id + "_attc_table.res"),
                    "-E", "10",
                    model_attc,
                    replicon_path]
    try:
        _log.debug("run cmsearch: {}".format(' '.join(cmsearch_cmd)))
        returncode = call(cmsearch_cmd)
    except Exception as err:
        raise RuntimeError("{0} failed : {1}".format(' '.join(cmsearch_cmd), err))
    if returncode != 0:
        raise RuntimeError("{0} failed returncode = {1}".format(' '.join(cmsearch_cmd), returncode))


def find_attc_max(integrons, replicon, distance_threshold,
                  model_attc_path, max_attc_size, circular=True, outfile="attC_max_1.res", out_dir='.', cpu=1):
    """
    Look for attC site with cmsearch --max option which remove all heuristic filters.
    As this option make the algorithm way slower, we only run it in the region around a
    hit. We call it local_max or eagle_eyes.

    **Default hit**
    ::
                         attC
        __________________-->____-->_________-->_____________
        ______<--------______________________________________
                 intI
                      ^-------------------------------------^
                     Search-space with --local_max

    **Updated hit**
    ::

                         attC          ***         ***
        __________________-->____-->___-->___-->___-->_______
        ______<--------______________________________________
                 intI

    :param integrons: the integrons may contain or not attC or intI.
    :type integrons: list of :class:`Integron` objects.
    :param replicon: replicon where the integrons were found (genomic fasta file).
    :type replicon: :class:`Bio.Seq.SeqRecord` object.
    :param int distance_threshold: the maximal distance between 2 elements to aggregate them.
    :param str model_attc_path: path to the attc model (Covariance Matrix).
    :param int max_attc_size: maximum value fot the attC size.
    :param bool circular: True if replicon is circular, False otherwise.
    :param str outfile: the name of cmsearch result file.
    :param int cpu: call local_max with the right number of cpu
    :return:
    :rtype: :class:`pd.DataFrame` object

    """
    size_replicon = len(replicon)
    columns = ['Accession_number', 'cm_attC', 'cm_debut', 'cm_fin', 'pos_beg', 'pos_end', 'sens', 'evalue']
    data_type = {'Accession_number': 'str', 'cm_attC': 'str',
                 'cm_debut': 'int', 'cm_fin': 'int',
                 'pos_beg': 'int', 'pos_end': 'int', }
    max_final = pd.DataFrame(columns=columns)
    max_final = max_final.astype(dtype=data_type)
    for i in integrons:
        max_elt = pd.DataFrame(columns=columns)
        max_elt = max_elt.astype(dtype=data_type)
        full_element = i.describe()

        if all(full_element.type == "complete"):
            # Where is the integrase compared to the attc sites (no matter the strand) :
            integrase_is_left = ((full_element[full_element.type_elt == "attC"].pos_beg.values[0] -
                                  full_element[full_element.annotation == "intI"].pos_end.values[0]) % size_replicon <
                                 (full_element[full_element.annotation == "intI"].pos_beg.values[0] -
                                  full_element[full_element.type_elt == "attC"].pos_end.values[-1]) % size_replicon)

            if integrase_is_left:
                window_beg = full_element[full_element.annotation == "intI"].pos_end.values[0]
                distance_threshold_left = 0
                window_end = full_element[full_element.type_elt == "attC"].pos_end.values[-1]
                distance_threshold_right = distance_threshold

            else:  # is right
                window_beg = full_element[full_element.type_elt == "attC"].pos_beg.values[0]
                distance_threshold_left = distance_threshold
                window_end = full_element[full_element.annotation == "intI"].pos_end.values[-1]
                distance_threshold_right = 0

            if circular:
                window_beg = (window_beg - distance_threshold_left) % size_replicon
                window_end = (window_end + distance_threshold_right) % size_replicon
            else:
                window_beg = max(0, window_beg - distance_threshold_left)
                window_end = min(size_replicon, window_end + distance_threshold_right)

            strand = "top" if full_element[full_element.type_elt == "attC"].strand.values[0] == 1 else "bottom"
            df_max = local_max(replicon, window_beg, window_end, model_attc_path,
                               strand_search=strand, out_dir=out_dir,
                               cpu_nb=cpu)
            max_elt = pd.concat([max_elt, df_max])

            # If we find new attC after the last found with default algo and if the integrase is on the left
            # (We don't expand over the integrase) :
            # pos_beg - pos_end so it's the same, the distance will always be > distance_threshold

            go_left = (full_element[full_element.type_elt == "attC"].pos_beg.values[0] - df_max.pos_end.values[0]
                       ) % size_replicon < distance_threshold and not integrase_is_left
            go_right = (df_max.pos_beg.values[-1] - full_element[full_element.type_elt == "attC"].pos_end.values[-1]
                        ) % size_replicon < distance_threshold and integrase_is_left
            max_elt = expand(replicon,
                             window_beg, window_end, max_elt, df_max,
                             circular, distance_threshold, max_attc_size,
                             model_attc_path,
                             search_left=go_left, search_right=go_right,
                             out_dir=out_dir, cpu=cpu)

        elif all(full_element.type == "CALIN"):
            if full_element[full_element.pos_beg.isin(max_final.pos_beg)].empty:
                # if cluster don't overlap already max-searched region
                window_beg = full_element[full_element.type_elt == "attC"].pos_beg.values[0]
                window_end = full_element[full_element.type_elt == "attC"].pos_end.values[-1]
                if circular:
                    window_beg = (window_beg - distance_threshold) % size_replicon
                    window_end = (window_end + distance_threshold) % size_replicon
                else:
                    window_beg = max(0, window_beg - distance_threshold)
                    window_end = min(size_replicon, window_end + distance_threshold)
                strand = "top" if full_element[full_element.type_elt == "attC"].strand.values[0] == 1 else "bottom"
                df_max = local_max(replicon, window_beg, window_end,
                                   model_attc_path,
                                   strand_search=strand,
                                   out_dir=out_dir, cpu_nb=cpu)
                max_elt = pd.concat([max_elt, df_max])

                if not df_max.empty:  # Max can sometimes find bigger attC than permitted
                    go_left = (full_element[full_element.type_elt == "attC"].pos_beg.values[0] - df_max.pos_end.values[0]
                               ) % size_replicon < distance_threshold
                    go_right = (df_max.pos_beg.values[-1] - full_element[full_element.type_elt == "attC"].pos_end.values[-1]
                                ) % size_replicon < distance_threshold
                    max_elt = expand(replicon,
                                     window_beg, window_end, max_elt, df_max,
                                     circular, distance_threshold, max_attc_size,
                                     model_attc_path,
                                     search_left=go_left, search_right=go_right,
                                     out_dir=out_dir, cpu=cpu)

        elif all(full_element.type == "In0"):
            if all(full_element.model != "Phage_integrase"):
                window_beg = full_element[full_element.annotation == "intI"].pos_beg.values[0]
                window_end = full_element[full_element.annotation == "intI"].pos_end.values[-1]
                if circular:
                    window_beg = (window_beg - distance_threshold) % size_replicon
                    window_end = (window_end + distance_threshold) % size_replicon
                else:
                    window_beg = max(0, window_beg - distance_threshold)
                    window_end = min(size_replicon, window_end + distance_threshold)
                df_max = local_max(replicon,
                                   window_beg, window_end,
                                   model_attc_path,
                                   strand_search=strand,
                                   out_dir=out_dir, cpu_nb=cpu)
                max_elt = pd.concat([max_elt, df_max])
                if not max_elt.empty:
                    max_elt = expand(replicon,
                                     window_beg, window_end, max_elt, df_max,
                                     circular, distance_threshold, max_attc_size,
                                     model_attc_path,
                                     search_left=True, search_right=True,
                                     out_dir=out_dir, cpu=cpu)

        max_final = pd.concat([max_final, max_elt])
        max_final.drop_duplicates(subset=max_final.columns[:-1], inplace=True)
        max_final.index = list(range(len(max_final)))
    return max_final
