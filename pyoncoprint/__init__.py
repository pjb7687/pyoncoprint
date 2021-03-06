import numpy as np
import pandas as pd

from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MaxNLocator
from matplotlib.lines import Line2D
from matplotlib.transforms import Affine2D
from matplotlib.legend_handler import HandlerLine2D
import matplotlib.gridspec as gridspec
from mpl_toolkits.axes_grid1 import make_axes_locatable, host_subplot

from numbers import Number
from copy import copy


def _get_text_bbox(t, ax, x=0, y=0, scale=[1, 1], fontdict=None):
    is_str = isinstance(t, str)
    if is_str:
        t = ax.text(x, y, t, fontdict=fontdict)
    bb = t.get_window_extent(ax.figure.canvas.get_renderer()).transformed(ax.transData.inverted()).transformed(Affine2D().scale(*scale))
    if is_str:
        t.remove()
    return bb

    
class OncoPrint:
    def __init__(self, recurrence_matrix, genes=None, samples=None, seperator=","):
        if isinstance(recurrence_matrix, pd.DataFrame):
            if samples is None:
                samples = recurrence_matrix.columns
            if genes is None:
                genes = recurrence_matrix.index
            mat = recurrence_matrix.to_numpy()
        else:
            mat = recurrence_matrix
        
        if genes is None:
            genes = np.array(["Gene %d"%i for i in range(1, arr.shape[0] + 1)])
        if samples is None:
            samples = np.array(["Sample %d"%i for i in range(1, arr.shape[1] + 1)])
        
        _, uniq_idx = np.unique(genes, return_index=True)
        if len(uniq_idx) != len(genes):
            dedup_mat = []
            dedup_genes = genes[np.sort(uniq_idx)]
            for g in dedup_genes:
                rows = mat[genes == g, :]
                joined_row = rows[0]
                for ridx in range(1, len(rows)):
                    for cidx in range(len(samples)):
                        if self._is_valid_string(joined_row[cidx]) and self._is_valid_string(rows[ridx][cidx]):
                            joined_row[cidx] += seperator + rows[ridx][cidx]
                        elif self._is_valid_string(rows[ridx][cidx]):
                            joined_row[cidx] = rows[ridx][cidx]
                dedup_mat.append(joined_row)
            self.mat = np.array(dedup_mat)
            self.genes = dedup_genes
        else:
            self.mat = mat
            self.genes = genes
            
        self.seperator = seperator
        self.samples = samples   
        
    def _is_valid_string(self, s):
        return isinstance(s, str) and len(s) > 0
    
    def _sort_genes_default(self):
        cntmat = np.zeros_like(self.sorted_mat, dtype=int)
        for i in range(self.sorted_mat.shape[0]):
            for j in range(self.sorted_mat.shape[1]):
                if self._is_valid_string(self.sorted_mat[i,j]):
                    cntmat[i,j] = len(np.unique(self.sorted_mat[i,j].split(self.seperator)))
        
        sorted_indices = np.argsort(np.sum(cntmat, axis=1))[::-1] # gene order
        self.sorted_genes = self.genes[sorted_indices]
        self.sorted_mat = self.sorted_mat[sorted_indices, :]
        
    def _sort_samples_default(self, mutation_types):
        mutation_to_weight = {mut: i for i, mut in enumerate(mutation_types[::-1], start=1)}
        weighted_filpped_cntmat = np.zeros_like(self.sorted_mat, dtype=int)
        for i in range(self.sorted_mat.shape[0]):
            for j in range(self.sorted_mat.shape[1]):
                if self._is_valid_string(self.sorted_mat[i,j]):
                    for mut in np.unique(self.sorted_mat[i,j].split(self.seperator)):
                        weighted_filpped_cntmat[self.sorted_mat.shape[0] - i - 1, j] += mutation_to_weight.get(mut, 0)
        sorted_indices = np.lexsort(weighted_filpped_cntmat)[::-1]
        self.sorted_samples = self.samples[sorted_indices]
        self.sorted_mat = self.sorted_mat[:, sorted_indices]
        
    def oncoprint(self, markers, annotations={},
                  title="",
                  gene_sort_method='default',
                  sample_sort_method='default',
                  figsize=[50, 20],
                  is_topplot = True,
                  is_rightplot = True,
                  is_legend = True,              
                  cell_background="#dddddd", gap=0.3,
                  ratio_template="{0:.0%}"):
        mutation_types = [b[0] for b in sorted(markers.items(), key=lambda a: a[1].get('zindex', 1))]
        self.sorted_mat = self.mat
        self.sorted_genes = self.genes
        self.sorted_samples = self.samples
        if gene_sort_method != 'unsorted':
            if gene_sort_method == 'default':
                self._sort_genes_default()
            else:
                print("Warning: gene sorting method '%s' is not supported."%gene_sort_method)
        if sample_sort_method != 'unsorted':
            if sample_sort_method == 'default':
                self._sort_samples_default(mutation_types)
            else:
                print("Warning: sample sorting method '%s' is not supported."%sample_sort_method)

        if isinstance(gap, Number):
            gap = np.array([gap, gap])
        else:
            assert len(gap) == 2, "The length of 'gap' is only allowed to be 2."
            gap = np.array(gap)
            
        backgrounds = []
        background_lengths = 1.0 - gap
        t_scale = Affine2D().scale(*background_lengths)
        patch_mutations = defaultdict(lambda: [[], []])
        scatter_mutations = defaultdict(lambda: [[], []])
        stacked_counts_top = np.zeros([len(mutation_types), self.sorted_mat.shape[1]])
        stacked_counts_right = np.zeros([len(mutation_types), self.sorted_mat.shape[0]])
        counts_left = np.zeros(self.sorted_mat.shape[0])
        for i in range(self.sorted_mat.shape[0]):
            for j in range(self.sorted_mat.shape[1]):
                backgrounds.append(Rectangle(-background_lengths / 2.0 + (j, i, ), *background_lengths))
                if self._is_valid_string(self.sorted_mat[i,j]):
                    counts_left[i] += 1
                    for mut in np.unique(self.sorted_mat[i,j].split(self.seperator)):
                        assert mut in mutation_types, "Marker for '%s' is not defined."%mut
                        stacked_counts_top[mutation_types.index(mut), j] += 1
                        stacked_counts_right[mutation_types.index(mut), i] += 1
                        ms = markers[mut]
                        if isinstance(ms['marker'], str) and (ms['marker'] == 'fill' or ms['marker'] == 'rect'):
                            patch_mutations[mut][0].append(Rectangle((0, 0), 1, 1))
                            patch_mutations[mut][1].append((j, i, ))
                        elif isinstance(ms['marker'], Patch):
                            patch_mutations[mut][0].append(copy(ms['marker']))
                            patch_mutations[mut][1].append((j, i, ))
                        else:
                            scatter_mutations[mut][0].append(j)
                            scatter_mutations[mut][1].append(i)
        is_annot = len(annotations) > 0
        if is_annot:
            sorted_annotations = sorted(annotations.items(), key=lambda e: annotations[e[0]].get('order'))[::-1]
            ax_annot_yticks = []
            ax_annot_patches = []
            for i, (annot_type, annot_dic) in enumerate(sorted_annotations):
                annots = annot_dic['annotations']
                annot_colors = annot_dic['colors']
                ax_annot_yticks.append(annot_type)
                for j, annot in enumerate(annots):
                    if self._is_valid_string(annot):
                        p = Rectangle(-background_lengths / 2.0 + (j, i, ), *background_lengths, color=annot_colors[annot], lw=0)
                        ax_annot_patches.append(p)
                    elif hasattr(type(annot), '__iter__'):
                        annot_item_bottom = 0.0
                        annot_item_sum = np.sum(annot, dtype=float)
                        if annot_item_sum > 0:
                            for annot_item in annot:
                                annot_item_height = background_lengths[1] * annot_item / annot_item_sum
                                p = Rectangle(-background_lengths / 2.0 + (j, i + annot_item_bottom, ),
                                              background_lengths[0], annot_item_height, color=annot_colors[annot_item], lw=0)
                                annot_item_bottom += annot_item_height
                                ax_annot_patches.append(p)
                        else:
                            p = Rectangle(-background_lengths / 2.0 + (j, i, ), *background_lengths, color=cell_background, lw=0)
                            ax_annot_patches.append(p)
                    else:
                        p = Rectangle(-background_lengths / 2.0 + (j, i, ), *background_lengths, color=cell_background, lw=0)
                        ax_annot_patches.append(p)
            ax_annot_pc = PatchCollection(ax_annot_patches, match_original=True)
            
        f = plt.figure(figsize=figsize)
        ax = host_subplot(111)
        ax_divider = make_axes_locatable(ax)
        
        ax_xticks = range(len(self.sorted_samples))
        ax_yticks = range(len(self.sorted_genes))
        ax.set_xticks(ax_xticks)
        ax.set_xticklabels(self.sorted_samples)
        ax.tick_params(axis='x', rotation=90)
        ax.set_yticks(ax_yticks)
        ax.set_yticklabels([ratio_template.format(e/float(self.mat.shape[1])) for e in counts_left])
        ax.tick_params(top=False, bottom=False, left=False, right=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.add_collection(PatchCollection(backgrounds, color=cell_background, linewidth=0))
        legend_mut_to_patch = {}
        legend_mut_to_scatter = {}
        for mut in mutation_types:
            ms = markers[mut]
            mk = ms['marker']
            if mut in patch_mutations:
                patches, coords = patch_mutations[mut]
                w, h = background_lengths * (ms.get('width', 1.0), ms.get('height', 1.0), )
                pc_kwargs = {k: v for k, v in ms.items() if not k in ('marker', 'width', 'height', 'zindex', )}
                if isinstance(mk, str) and (mk == 'fill' or mk == 'rect'):
                    pc_kwargs['linewidth'] = pc_kwargs.get('linewidth', 0)
                if is_legend:
                    legend_p = copy(patches[0])
                    legend_mut_to_patch[mut] = (legend_p, w, h, pc_kwargs)
                t_scale = Affine2D().scale(w, -h)
                for p, (x, y) in zip(patches, coords):
                    p.set_transform(p.get_transform() + t_scale + Affine2D().translate(x - w * 0.5, y + h * 0.5))
                pc = PatchCollection(patches, **pc_kwargs)
                ax.add_collection(pc)
            elif mut in scatter_mutations:
                scatter_kwargs = {k: v for k, v in markers[mut].items() if k != 'zindex'}
                if is_legend:
                    legend_mut_to_scatter[mut] = scatter_kwargs
                ax.scatter(*scatter_mutations[mut], **scatter_kwargs)

        ax2 = ax.twinx()
        ax.get_shared_y_axes().join(ax, ax2)
        ax2.set_yticks(ax_yticks)
        ax2.set_yticklabels(self.sorted_genes)
        ax2.tick_params(top=False, bottom=False, left=False, right=False)
        for spine in ax2.spines.values():
            spine.set_visible(False)

        ax_annot = None
        ax_top = None
        ax_right = None
        ax_legend = None
        #ratio_gap = gap / (len(self.sorted_genes) - gap)
        if is_annot:
            ratio_annot = (len(annotations) - gap[1]) / (len(self.sorted_genes) - gap[1])
            ax_annot = ax_divider.append_axes("top", size="{0:.6%}".format(ratio_annot), pad=0.2)
            ax_annot.add_collection(ax_annot_pc)
            ax_annot.set_ylim([len(annotations) - 1 + background_lengths[1]/2.0, -background_lengths[1]/2.0]) 
            ax_annot.set_yticks(range(len(ax_annot_yticks)))
            ax_annot.set_yticklabels(ax_annot_yticks)
            ax.get_shared_x_axes().join(ax, ax_annot)
            ax_annot.tick_params(top=False, bottom=False, left=False, right=False,
                                 labeltop=False, labelbottom=False, labelleft=True, labelright=False)
            for spine in ax_annot.spines.values():
                spine.set_visible(False)
        if is_topplot:
            ax_top = ax_divider.append_axes("top", size=1, pad=0.2)
            ax.get_shared_x_axes().join(ax, ax_top)
            bottom = np.zeros(self.mat.shape[1])
            for idx, cnts in enumerate(stacked_counts_top):
                col = markers[mutation_types[idx]]['color']
                ax_top.bar(ax_xticks, cnts, color=col, width=background_lengths[0], bottom=bottom)
                bottom += cnts
            ax_top.yaxis.set_major_locator(MaxNLocator(integer=True))
            #ax_top.set_xlim(ax_xlim)
            ax_top.tick_params(top=False, bottom=False, left=True, right=False,
                               labeltop=False, labelbottom=False, labelleft=True, labelright=False)
            for idx, spine in enumerate(ax_top.spines.values()):
                if idx == 0:
                    continue
                spine.set_visible(False)
        if is_rightplot:
            ax_right = ax_divider.append_axes("right", size=2, pad=1)
            ax.get_shared_y_axes().join(ax, ax_right)
            left = np.zeros(self.mat.shape[0])
            for idx, cnts in enumerate(stacked_counts_right):
                col = markers[mutation_types[idx]]['color']
                ax_right.barh(ax_yticks, cnts, color=col, height=background_lengths[1], left=left)
                left += cnts
            ax_right.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax_right.tick_params(axis='x', rotation=90)
            ax_right.tick_params(top=True, bottom=False, left=False, right=False,
                                 labeltop=True, labelbottom=False, labelleft=False, labelright=False)
            for idx, spine in enumerate(ax_right.spines.values()):
                if idx == 3:
                    continue
                spine.set_visible(False)
                
        ax_xlim = [-background_lengths[0]/2.0, self.mat.shape[1] - 1 + background_lengths[0]/2.0]                
        ax_ylim = [self.mat.shape[0] - 1 + background_lengths[1]/2.0, -background_lengths[1]/2.0]
        ax.set_xlim(ax_xlim)
        ax.set_ylim(ax_ylim)
        
        if is_legend:
            ax_size = ax.transAxes.transform([1, 1]) / f.dpi
            ax_size_reduced = copy(ax_size)
            if is_rightplot:
                ax_size_reduced[0] -= 3 # pad + size of the plot
            ax_scale = ax_size / ax_size_reduced
            bb = _get_text_bbox(" ", ax, x=0, y=0, scale=ax_scale)
            tw_space = abs(bb.width)
            text_height = abs(bb.height)
            line_height = max(text_height, background_lengths[1])
            text_left_offset, text_top_offset = -bb.xmin, -bb.ymax
            legend_items = []
            pad_x, pad_y = -gap
            pad_x += tw_space * 5
            cur_x = pad_x
            cur_y = pad_y
            legend_patches = []
            legend_texts = []
            legend_pcs = []
            legend_scatters = []
            legend_yticks = [0.5, ]
            legend_titles = ['Genetic Alteration', ]

            gap_handle_to_text = tw_space * 2

            def add_legend_item(label, col, cur_x, cur_y, is_first, is_mut):
                legend_item_width = background_lengths[0] + gap_handle_to_text + abs(_get_text_bbox(label, ax, scale=ax_scale).width)
                if cur_x + legend_item_width > ax_xlim[1] and not is_first:
                    cur_x = pad_x
                    cur_y += line_height + line_height / 2.0
                p = Rectangle((cur_x, cur_y), *background_lengths, color=col, lw=0)
                #p = Rectangle((0, 0), 1, 1, color=col)
                #p.set_transform(Affine2D().scale(*background_lengths).translate(cur_x, cur_y))
                legend_patches.append(p)
                if is_mut:
                    if label in legend_mut_to_patch:
                        p, w, h, pc_kwargs = legend_mut_to_patch[label]
                        p.set_transform(p.get_transform() + Affine2D().scale(w, -h).translate(cur_x, cur_y + 0.5 + h * 0.5))
                        legend_pcs.append(PatchCollection([p], **pc_kwargs))
                    elif label in legend_mut_to_scatter:
                        scatter_kwargs = legend_mut_to_scatter[label]
                        legend_scatters.append((background_lengths * 0.5 + (cur_x, cur_y, ), scatter_kwargs))
                        
                legend_texts.append((label,
                                     cur_x + text_left_offset + background_lengths[0] + gap_handle_to_text,
                                     cur_y + text_top_offset + 0.5 + text_height / 2.0))
                cur_x += legend_item_width + tw_space * 10
                return cur_x, cur_y

            is_first = True
            for mut in mutation_types:
                #if is_first:
                #    debug_x = cur_x
                #    debug_y = cur_y
                cur_x, cur_y = add_legend_item(mut, cell_background, cur_x, cur_y, is_first, True)
                is_first = False

            if is_annot:
                for annot_type, annot_dic in sorted_annotations:
                    cur_x = pad_x
                    cur_y += line_height * 2.0
                    annot_colors = annot_dic['colors']
                    legend_titles.append(annot_type)
                    legend_yticks.append(cur_y + 0.5)
                    is_first = True
                    for annot_label, annot_color in sorted(annot_colors.items(), key=lambda e: e[0]):
                        cur_x, cur_y = add_legend_item(annot_label, annot_color, cur_x, cur_y, is_first, False)
                        is_first = False

            ax_legend_height = cur_y + 1
            ax_legend_height_ratio = ax_legend_height / (len(self.sorted_genes) - gap[1])
            ax_legend = ax_divider.append_axes("bottom", size="{0:.6%}".format(ax_legend_height_ratio), pad=1.5)
            ax_legend.set_xlim(ax_xlim)
            ax_legend.set_ylim([ax_legend_height, 0])
            
            #bb = _get_text_bbox("Amplification", ax)
            #p_bbox = Rectangle((debug_x + text_left_offset + background_lengths[0] + gap_handle_to_text, debug_y + text_top_offset + 0.5 + text_height / 2.0), abs(bb.width), -abs(bb.height))
            #legend_patches.append(p_bbox)

            ax_legend.set_yticks(legend_yticks)
            ax_legend.set_yticklabels(legend_titles)
            ax_legend.tick_params(top=False, bottom=False, left=False, right=False,
                                 labeltop=False, labelbottom=False, labelleft=True, labelright=False)
            for spine in ax_legend.spines.values():
                spine.set_visible(False)
            ax_legend.set_navigate(False)
            ax_legend.add_collection(PatchCollection(legend_patches, match_original=True))
            for pc in legend_pcs:
                ax_legend.add_collection(pc)
            for t, x, y in legend_texts:
                ax_legend.text(x, y, t)
            for (x, y), scatter_kwargs in legend_scatters:
                ax_legend.scatter([x], [y], **scatter_kwargs)

        if title != "":
            ttl = f.suptitle(title)
 
        return f, (ax, ax2, ax_top, ax_annot, ax_right, ax_legend)
        