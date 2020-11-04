import pytest

from dnaio import Sequence
from cutadapt.adapters import BackAdapter, PrefixAdapter, IndexedPrefixAdapters
from cutadapt.modifiers import (UnconditionalCutter, NEndTrimmer, QualityTrimmer,
    Shortener, AdapterCutter, PairedAdapterCutter, ModificationInfo, ZeroCapper,
    Renamer, ReverseComplementer)


def test_unconditional_cutter():
    UnconditionalCutter(length=5)
    read = Sequence('r1', 'abcdefg')

    info = ModificationInfo(read)
    assert UnconditionalCutter(length=2)(read, info).sequence == 'cdefg'
    assert info.cut_prefix == 'ab'
    assert not hasattr(info, 'cut_suffix')

    info = ModificationInfo(read)
    assert UnconditionalCutter(length=-2)(read, info).sequence == 'abcde'
    assert info.cut_suffix == 'fg'
    assert not hasattr(info, 'cut_prefix')

    assert UnconditionalCutter(length=100)(read, info).sequence == ''
    assert UnconditionalCutter(length=-100)(read, info).sequence == ''


def test_reverse_complementer():
    adapters = [
        PrefixAdapter("TTATTTGTCT"),
        PrefixAdapter("TCCGCACTGG"),
    ]
    adapter_cutter = AdapterCutter(adapters, index=False)
    reverse_complementer = ReverseComplementer(adapter_cutter)

    read = Sequence("r", "ttatttgtctCCAGCTTAGACATATCGCCT")
    info = ModificationInfo(read)
    trimmed = reverse_complementer(read, info)
    assert trimmed.sequence == "CCAGCTTAGACATATCGCCT"
    assert not info.is_rc

    read = Sequence("r", "CAACAGGCCACATTAGACATATCGGATGGTagacaaataa")
    info = ModificationInfo(read)
    trimmed = reverse_complementer(read, info)
    assert trimmed.sequence == "ACCATCCGATATGTCTAATGTGGCCTGTTG"
    assert info.is_rc


def test_zero_capper():
    zc = ZeroCapper()
    read = Sequence("r1", "ACGT", "# !%")
    result = zc(read, ModificationInfo(read))
    assert result.sequence == "ACGT"
    assert result.qualities == "#!!%"


def test_nend_trimmer():
    trimmer = NEndTrimmer()
    seqs = ['NNNNAAACCTTGGNNN', 'NNNNAAACNNNCTTGGNNN', 'NNNNNN']
    trims = ['AAACCTTGG', 'AAACNNNCTTGG', '']
    for seq, trimmed in zip(seqs, trims):
        _seq = Sequence('read1', seq, qualities='#'*len(seq))
        _trimmed = Sequence('read1', trimmed, qualities='#'*len(trimmed))
        assert trimmer(_seq, ModificationInfo(_seq)) == _trimmed


def test_quality_trimmer():
    read = Sequence('read1', 'ACGTTTACGTA', '##456789###')

    qt = QualityTrimmer(10, 10, 33)
    assert qt(read, ModificationInfo(read)) == Sequence('read1', 'GTTTAC', '456789')

    qt = QualityTrimmer(0, 10, 33)
    assert qt(read, ModificationInfo(read)) == Sequence('read1', 'ACGTTTAC', '##456789')

    qt = QualityTrimmer(10, 0, 33)
    assert qt(read, ModificationInfo(read)) == Sequence('read1', 'GTTTACGTA', '456789###')


def test_shortener():
    read = Sequence('read1', 'ACGTTTACGTA', '##456789###')

    shortener = Shortener(0)
    assert shortener(read, ModificationInfo(read)) == Sequence('read1', '', '')

    shortener = Shortener(1)
    assert shortener(read, ModificationInfo(read)) == Sequence('read1', 'A', '#')

    shortener = Shortener(5)
    assert shortener(read, ModificationInfo(read)) == Sequence('read1', 'ACGTT', '##456')

    shortener = Shortener(100)
    assert shortener(read, ModificationInfo(read)) == read


def test_adapter_cutter_indexing():
    adapters = [
        PrefixAdapter(sequence, max_errors=1, indels=False)
        for sequence in ["ACGAT", "GGAC", "TTTACTTA", "TAACCGGT", "GTTTACGTA", "CGATA"]
    ]
    ac = AdapterCutter(adapters)
    assert len(ac.adapters) == 1
    assert isinstance(ac.adapters[0], IndexedPrefixAdapters)

    ac = AdapterCutter(adapters, index=False)
    assert len(ac.adapters) == len(adapters)


@pytest.mark.parametrize("action,expected_trimmed1,expected_trimmed2", [
    (None, "CCCCGGTTAACCCC", "TTTTAACCGGTTTT"),
    ("trim", "CCCC", "TTTT"),
    ("lowercase", "CCCCggttaacccc", "TTTTaaccggtttt"),
    ("mask", "CCCCNNNNNNNNNN", "TTTTNNNNNNNNNN")
])
def test_paired_adapter_cutter_actions(action, expected_trimmed1, expected_trimmed2):
    a1 = BackAdapter("GGTTAA")
    a2 = BackAdapter("AACCGG")
    s1 = Sequence("name", "CCCCGGTTAACCCC")
    s2 = Sequence("name", "TTTTAACCGGTTTT")
    pac = PairedAdapterCutter([a1], [a2], action=action)
    info1 = ModificationInfo(s1)
    info2 = ModificationInfo(s2)
    trimmed1, trimmed2 = pac(s1, s2, info1, info2)
    assert expected_trimmed1 == trimmed1.sequence
    assert expected_trimmed2 == trimmed2.sequence


class TestRenamer:
    def test_header_template_variable(self):
        renamer = Renamer("{header} extra")
        read = Sequence("theid thecomment", "ACGT")
        info = ModificationInfo(read)
        assert renamer(read, info).name == "theid thecomment extra"

    def test_id_template_variable(self):
        renamer = Renamer("{id} extra")
        read = Sequence("theid thecomment", "ACGT")
        info = ModificationInfo(read)
        assert renamer(read, info).name == "theid extra"

    def test_comment_template_variable(self):
        renamer = Renamer("{id}_extra {comment}")
        read = Sequence("theid thecomment", "ACGT")
        info = ModificationInfo(read)
        assert renamer(read, info).name == "theid_extra thecomment"

    def test_comment_template_variable_missing_comment(self):
        renamer = Renamer("{id}_extra {comment}")
        read = Sequence("theid", "ACGT")
        info = ModificationInfo(read)
        assert renamer(read, info).name == "theid_extra "

    def test_cut_prefix_template_variable(self):
        renamer = Renamer("{id}_{cut_prefix} {comment}")
        read = Sequence("theid thecomment", "ACGT")
        info = ModificationInfo(read)
        info.cut_prefix = "TTAAGG"
        assert renamer(read, info).name == "theid_TTAAGG thecomment"
