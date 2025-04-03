import json
import correctionlib
import numpy as np
import awkward as ak
from typing import Type
from pathlib import Path
from .utils import unflat_sf
from coffea.analysis_tools import Weights
from analysis.selections import trigger_match
from analysis.corrections.utils import pog_years, get_pog_json


# https://twiki.cern.ch/twiki/bin/view/CMS/MuonUL2016
# https://twiki.cern.ch/twiki/bin/view/CMS/MuonUL2017
# https://twiki.cern.ch/twiki/bin/view/CMS/MuonUL2018


def get_id_wps(muons):
    return {
        # cutbased ID working points
        "loose": muons.looseId,
        "medium": muons.mediumId,
        "tight": muons.tightId,
    }


def get_iso_wps(muons):
    return {
        "loose": (
            muons.pfRelIso04_all < 0.25
            if hasattr(muons, "pfRelIso04_all")
            else muons.pfRelIso03_all < 0.25
        ),
        "medium": (
            muons.pfRelIso04_all < 0.20
            if hasattr(muons, "pfRelIso04_all")
            else muons.pfRelIso03_all < 0.20
        ),
        "tight": (
            muons.pfRelIso04_all < 0.15
            if hasattr(muons, "pfRelIso04_all")
            else muons.pfRelIso03_all < 0.15
        ),
    }


class MuonCorrector:
    """
    Muon corrector class

    Parameters:
    -----------
    events:
        events collection
    weights:
        Weights object from coffea.analysis_tools
    year:
        Year of the dataset  {'2016preVFP', '2016postVFP', '2017', '2018'}
    variation:
        syst variation
    id_wp:
        ID working point {'loose', 'medium', 'tight'}
    iso_wp:
        Iso working point {'loose', 'medium', 'tight'}
    """

    def __init__(
        self,
        events,
        weights: Type[Weights],
        year: str = "2017",
        variation: str = "nominal",
        id_wp: str = "tight",
        iso_wp: str = "tight",
    ) -> None:
        self.events = events
        self.muons = events.selected_muons
        self.variation = variation
        self.id_wp = id_wp
        self.iso_wp = iso_wp

        # flat muon array
        self.m, self.n = ak.flatten(self.muons), ak.num(self.muons)

        # weights container
        self.weights = weights

        # define correction set
        self.cset = correctionlib.CorrectionSet.from_file(
            get_pog_json(json_name="muon", year=year)
        )
        self.year = year
        self.pog_year = pog_years[year]

    def add_reco_weight(self):
        """
        add muon RECO scale factors to weights container
        """
        # get muons within SF binning
        muon_pt_mask = self.m.pt >= 40.0
        muon_eta_mask = np.abs(self.m.eta) < 2.4
        in_muon_mask = muon_pt_mask & muon_eta_mask
        in_muons = self.m.mask[in_muon_mask]

        # get muons pT and abseta (replace None values with some 'in-limit' value)
        muon_pt = ak.fill_none(in_muons.pt, 40.0)
        muon_eta = np.abs(ak.fill_none(in_muons.eta, 0.0))

        # 'id' scale factors names
        reco_corrections = {
            "2016preVFP": "NUM_TrackerMuons_DEN_genTracks",
            "2016postVFP": "NUM_TrackerMuons_DEN_genTracks",
            "2017": "NUM_TrackerMuons_DEN_genTracks",
            "2018": "NUM_TrackerMuons_DEN_genTracks",
        }
        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset[reco_corrections[self.year]].evaluate(
                muon_eta, muon_pt, "nominal"
            ),
            in_muon_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset[reco_corrections[self.year]].evaluate(
                    muon_eta, muon_pt, "systup"
                ),
                in_muon_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset[reco_corrections[self.year]].evaluate(
                    muon_eta, muon_pt, "systdown"
                ),
                in_muon_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"muon_reco",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"muon_reco",
                weight=nominal_sf,
            )

    def add_id_weight(self):
        """
        add muon ID scale factors to weights container
        """
        # get muons that pass the id wp, and within SF binning
        muon_pt_mask = (self.m.pt > 15.0) & (self.m.pt < 199.999)
        muon_eta_mask = np.abs(self.m.eta) < 2.39
        muon_id_mask = get_id_wps(self.m)[self.id_wp]
        in_muon_mask = muon_pt_mask & muon_eta_mask & muon_id_mask
        in_muons = self.m.mask[in_muon_mask]

        # get muons pT and abseta (replace None values with some 'in-limit' value)
        muon_pt = ak.fill_none(in_muons.pt, 15.0)
        muon_eta = np.abs(ak.fill_none(in_muons.eta, 0.0))

        # 'id' scale factors names
        id_corrections = {
            "2016preVFP": {
                "loose": "NUM_LooseID_DEN_TrackerMuons",
                "medium": "NUM_MediumID_DEN_TrackerMuons",
                "tight": "NUM_TightID_DEN_TrackerMuons",
            },
            "2016postVFP": {
                "loose": "NUM_LooseID_DEN_TrackerMuons",
                "medium": "NUM_MediumID_DEN_TrackerMuons",
                "tight": "NUM_TightID_DEN_TrackerMuons",
            },
            "2017": {
                "loose": "NUM_LooseID_DEN_TrackerMuons",
                "medium": "NUM_MediumID_DEN_TrackerMuons",
                "tight": "NUM_TightID_DEN_TrackerMuons",
            },
            "2018": {
                "loose": "NUM_LooseID_DEN_TrackerMuons",
                "medium": "NUM_MediumID_DEN_TrackerMuons",
                "tight": "NUM_TightID_DEN_TrackerMuons",
            },
        }

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset[id_corrections[self.year][self.id_wp]].evaluate(
                muon_eta, muon_pt, "nominal"
            ),
            in_muon_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset[id_corrections[self.year][self.id_wp]].evaluate(
                    muon_eta, muon_pt, "systup"
                ),
                in_muon_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset[id_corrections[self.year][self.id_wp]].evaluate(
                    muon_eta, muon_pt, "systdown"
                ),
                in_muon_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"muon_id_{self.id_wp}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"muon_id_{self.id_wp}",
                weight=nominal_sf,
            )

    def add_iso_weight(self):
        """
        add muon Iso (LooseRelIso with mediumID) scale factors to weights container
        """
        # get 'in-limits' muons
        muon_pt_mask = self.m.pt > 29.0
        muon_eta_mask = np.abs(self.m.eta) < 2.39
        muon_id_mask = get_id_wps(self.m)[self.id_wp]
        muon_iso_mask = get_iso_wps(self.m)[self.iso_wp]
        in_muon_mask = muon_pt_mask & muon_eta_mask & muon_id_mask & muon_iso_mask
        in_muons = self.m.mask[in_muon_mask]

        # get muons pT and abseta (replace None values with some 'in-limit' value)
        muon_pt = ak.fill_none(in_muons.pt, 29.0)
        muon_eta = np.abs(ak.fill_none(in_muons.eta, 0.0))

        iso_corrections = {
            "2016preVFP": {
                "loose": {
                    "loose": "NUM_LooseRelIso_DEN_LooseID",
                    "medium": None,
                    "tight": None,
                },
                "medium": {
                    "loose": "NUM_LooseRelIso_DEN_MediumID",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_MediumID",
                },
                "tight": {
                    "loose": "NUM_LooseRelIso_DEN_TightIDandIPCut",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_TightIDandIPCut",
                },
            },
            "2016postVFP": {
                "loose": {
                    "loose": "NUM_LooseRelIso_DEN_LooseID",
                    "medium": None,
                    "tight": None,
                },
                "medium": {
                    "loose": "NUM_LooseRelIso_DEN_MediumID",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_MediumID",
                },
                "tight": {
                    "loose": "NUM_LooseRelIso_DEN_TightIDandIPCut",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_TightIDandIPCut",
                },
            },
            "2017": {
                "loose": {
                    "loose": "NUM_LooseRelIso_DEN_LooseID",
                    "medium": None,
                    "tight": None,
                },
                "medium": {
                    "loose": "NUM_LooseRelIso_DEN_MediumID",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_MediumID",
                },
                "tight": {
                    "loose": "NUM_LooseRelIso_DEN_TightIDandIPCut",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_TightIDandIPCut",
                },
            },
            "2018": {
                "loose": {
                    "loose": "NUM_LooseRelIso_DEN_LooseID",
                    "medium": None,
                    "tight": None,
                },
                "medium": {
                    "loose": "NUM_LooseRelIso_DEN_MediumID",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_MediumID",
                },
                "tight": {
                    "loose": "NUM_LooseRelIso_DEN_TightIDandIPCut",
                    "medium": None,
                    "tight": "NUM_TightRelIso_DEN_TightIDandIPCut",
                },
            },
        }

        correction_name = iso_corrections[self.year][self.id_wp][self.iso_wp]
        assert correction_name, "No Iso SF's available"

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset[correction_name].evaluate(muon_eta, muon_pt, "nominal"),
            in_muon_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset[correction_name].evaluate(muon_eta, muon_pt, "systup"),
                in_muon_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset[correction_name].evaluate(muon_eta, muon_pt, "systdown"),
                in_muon_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"muon_iso_{self.iso_wp}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"muon_iso_{self.iso_wp}",
                weight=nominal_sf,
            )

    def add_triggeriso_weight(self, hlt_paths) -> None:
        """
        add muon Trigger Iso (IsoMu24 or IsoMu27) weights

        trigger_mask:
            mask array of events passing the analysis trigger
        trigger_match_mask:
            mask array of DeltaR matched trigger objects
        """
        assert (
            self.id_wp == "tight" and self.iso_wp == "tight"
        ), "there's only available muon trigger SF for 'tight' ID and Iso"

        trigger_match_mask = np.zeros(len(self.events), dtype="bool")
        for hlt_path in hlt_paths:
            trig_match = trigger_match(
                leptons=self.muons,
                trigobjs=self.events.TrigObj,
                trigger_path=hlt_path,
            )
            trigger_match_mask = trigger_match_mask | trig_match

        trigger_mask = np.zeros(len(self.events), dtype="bool")

        for hlt_path in hlt_paths:
            if hlt_path in self.events.HLT.fields:
                trigger_mask = trigger_mask | self.events.HLT[hlt_path]

        # get 'in-limits' muons
        muon_pt_mask = (self.m.pt > 29.0) & (self.m.pt < 199.999)
        muon_eta_mask = np.abs(self.m.eta) < 2.399
        muon_id_mask = get_id_wps(self.m)[self.id_wp]
        muon_iso_mask = get_iso_wps(self.m)[self.iso_wp]

        trigger_mask = ak.flatten(ak.ones_like(self.muons.pt) * trigger_mask) > 0
        trigger_match_mask = ak.flatten(trigger_match_mask)

        in_muon_mask = (
            muon_pt_mask
            & muon_eta_mask
            & muon_id_mask
            & muon_iso_mask
            & trigger_mask
            & trigger_match_mask
        )
        in_muons = self.m.mask[in_muon_mask]

        # get muons transverse momentum and abs pseudorapidity (replace None values with some 'in-limit' value)
        muon_pt = ak.fill_none(in_muons.pt, 29.0)
        muon_eta = np.abs(ak.fill_none(in_muons.eta, 0.0))

        # scale factors keys
        sfs_keys = {
            "2016preVFP": "NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight",
            "2016postVFP": "NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight",
            "2017": "NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight",
            "2018": "NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight",
        }
        # get nominal scale factors
        sf = self.cset[sfs_keys[self.year]].evaluate(muon_eta, muon_pt, "nominal")
        nominal_sf = unflat_sf(
            sf,
            in_muon_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = self.cset[sfs_keys[self.year]].evaluate(muon_eta, muon_pt, "systup")
            up_sf = unflat_sf(
                up_sf,
                in_muon_mask,
                self.n,
            )
            down_sf = self.cset[sfs_keys[self.year]].evaluate(
                muon_eta, muon_pt, "systdown"
            )
            down_sf = unflat_sf(
                down_sf,
                in_muon_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"muon_triggeriso",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"muon_triggeriso",
                weight=nominal_sf,
            )