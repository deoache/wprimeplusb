import json
import copy
import correctionlib
import numpy as np
import awkward as ak
import importlib.resources
from typing import Type
from pathlib import Path
from .utils import unflat_sf
from coffea.analysis_tools import Weights
from analysis.corrections.utils import pog_years, get_pog_json


"""
TauID corrections

https://twiki.cern.ch/twiki/bin/viewauth/CMS/TauIDRecommendationForRun2
https://github.com/cms-tau-pog/TauIDSFs
https://github.com/uhh-cms/hh2bbtautau/blob/7666ed0426c87baa8d143ec26a216c3cadde513b/hbt/calibration/tau.py#L60

Good example:
https://github.com/schaefes/hh2bbtautau/blob/da6d47a7ddb2b1e7ffda06b8a96c6ddead2824b8/hbt/production/tau.py#L108

# genuine taus
* DeepTau2017v2p1VSjet (pt [-inf, inf); dm (0, 1, 2, 10, 11) ; genmatch (0, 1, 2, 3, 4, 5, 6 ); wp (Loose, Medium, Tight, VTight); wp_VSe (Tight, VVLoose );  syst ; flag (dm, pt))


# electrons faking taus
* DeepTau2017v2p1VSe = eta [0.0, 2.3); genmatch (0, 1); wp (Loose, Medium, Tight, VLoose, VTight, VVLoose, VVTight; syst (down, nom, up)

# muons faking taus
* DeepTau2017v2p1VSmu (eta [0.0, 2.3); genmatch (0, 2); wp (Loose, Medium, Tight, VLoose); syst (down, nom, up))

        
"""


class TauCorrector:
    def __init__(
        self,
        events,
        weights: Type[Weights],
        year: str = "2017",
        tau_vs_jet: str = "tight",
        tau_vs_ele: str = "tight",
        tau_vs_mu: str = "tight",
        variation: str = "nominal",
    ) -> None:

        # flat taus array
        taus = events.selected_taus
        self.events = events
        self.taus, self.n = ak.flatten(taus), ak.num(taus)

        # tau transverse momentum and pseudorapidity
        self.taus_pt = self.taus.pt
        self.taus_eta = self.taus.eta

        # tau genPartFlav and decayMode
        self.taus_genMatch = self.taus.genPartFlav
        self.taus_dm = self.taus.decayMode

        self.wp_map = {
            element.lower(): element
            for element in [
                "Loose",
                "Medium",
                "Tight",
                "VLoose",
                "VTight",
                "VVLoose",
                "VVTight",
            ]
        }

        self.weights = weights
        self.year = year
        self.year_key = year
        if year.startswith("2016"):
            self.year_key = "2016"
        # DeepTau working points
        self.tau_vs_jet = tau_vs_jet
        self.tau_vs_ele = tau_vs_ele
        self.tau_vs_mu = tau_vs_mu

        self.variation = variation

        # define correction set_id
        self.cset = correctionlib.CorrectionSet.from_file(
            get_pog_json(json_name="tau", year=self.year)
        )
        self.pog_year = pog_years[year]
        """
        Check: https://github.com/cms-tau-pog/TauFW/blob/43bc39474b689d9712107d53a953b38c3cd9d43e/PicoProducer/python/analysis/ModuleETau.py#L270 
        """

    # e -> tau_h fake rate SFs for DeepTau2017v2p1VSe
    # eta = (0, 2.3]; genMatch = 0,1; wp = Loose, Medium, Tight, VLoose, VTight, VVLoose, VVTight; syst: down, nom, up

    def add_id_weight_deeptauvse(self):
        """
        Sf is called with:

        evaluate(eta (real),  genmatch (int) , wp (string), syst (string))

        """
        # tau pseudorapidity range: [0, 2.3)
        tau_eta_mask = (self.taus_eta >= 0) & (self.taus_eta < 2.3)
        # GenMatch = 0 "unmatched", 1 "electron";
        tau_genMatch_mask = (self.taus_genMatch == 1) | (self.taus_genMatch == 3)
        in_tau_mask = tau_genMatch_mask & tau_eta_mask
        # get 'in-limits' taus
        in_limit_taus = self.taus.mask[in_tau_mask]
        # get pt and eta
        # fill Nones with some 'in-limit' value
        tau_eta = ak.fill_none(in_limit_taus.eta, 0)
        tau_genMatch = ak.fill_none(in_limit_taus.genPartFlav, 0.0)

        # syst
        syst = "nom"
        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset["DeepTau2017v2p1VSe"].evaluate(
                tau_eta, tau_genMatch, self.wp_map[self.tau_vs_ele], "nom"
            ),
            in_tau_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSe"].evaluate(
                    tau_eta, tau_genMatch, self.wp_map[self.tau_vs_ele], "up"
                ),
                in_tau_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSe"].evaluate(
                    tau_eta, tau_genMatch, self.wp_map[self.tau_vs_ele], "down"
                ),
                in_tau_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSe_{self.year_key}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSe_{self.year_key}",
                weight=nominal_sf,
            )
        return nominal_sf

    # mu -> tau_h fake rate SFs for DeepTau2017v2p1VSmu
    # eta = (0, 2.3]; genMatch = 0,2; wp = Loose, Medium, Tight, VLoose ; syst: down, nom, up

    def add_id_weight_deeptauvsmu(self):
        """
        Sf is called with:

        evaluate(eta (real),  genmatch (int) , wp (string), syst (string))

        """
        # tau pseudorapidity range: [0, 2.3)
        tau_eta_mask = (self.taus_eta >= 0) & (self.taus_eta < 2.3)
        # GenMatch = 0 "unmatched", 2 "muon";
        tau_genMatch_mask = (self.taus_genMatch == 2) | (self.taus_genMatch == 4)
        in_tau_mask = tau_genMatch_mask & tau_eta_mask
        # get 'in-limits' taus
        in_limit_taus = self.taus.mask[in_tau_mask]
        # get pt and etaF
        # fill Nones with some 'in-limit' value
        tau_eta = ak.fill_none(in_limit_taus.eta, 0)
        tau_genMatch = ak.fill_none(in_limit_taus.genPartFlav, 0.0)

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset["DeepTau2017v2p1VSmu"].evaluate(
                tau_eta, tau_genMatch, self.wp_map[self.tau_vs_mu], "nom"
            ),
            in_tau_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSmu"].evaluate(
                    tau_eta, tau_genMatch, self.wp_map[self.tau_vs_mu], "up"
                ),
                in_tau_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSmu"].evaluate(
                    tau_eta, tau_genMatch, self.wp_map[self.tau_vs_mu], "down"
                ),
                in_tau_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSmu_{self.year_key}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSmu_{self.year_key}",
                weight=nominal_sf,
            )
        return nominal_sf

    # By default, use the pT-dependent SFs with the 'pt' flag
    # pt = (-inf, inf); dm = 0, 1, 2, 10, 11; genmatch = 0, 1, 2, 3, 4, 5, 6; wp = Loose, Medium, Tight, VTight; wp_VSe = Tight, VVLoose; syst = down, nom, up; flag = dm, pt

    def add_id_weight_deeptauvsjet(self, flag: str = "pt"):
        """
        https://github.com/LEAF-HQ/LEAF/blob/d22cc55594a4b16d061c25dbf7ecdec04eedbc34/Analyzer/src/TauScaleFactorApplicatorJson.cc#L28

        Sf is called with:

        evaluate(pt (real),  dm (int), genmatch (int), wp (string), wp_VSe (string), syst (string), flag (string))

         - dm (decay mode): 0 (tau->pi); 1 (tau->rho->pi+pi0); 2 (tau->a1->pi+2pi0); 10 (tau->a1->3pi); 11 (tau->3pi+pi0)
         - getmatch: 0 or 6 = unmatched or jet, 1 or 3 = electron, 2 or 4 = muon, 5 = real tau
         - flag: We have worked in 'pt' = pT-dependent

        """
        # tau decayMode
        tau_dm_mask = (
            (self.taus_dm == 0)
            | (self.taus_dm == 1)
            | (self.taus_dm == 2)
            | (self.taus_dm == 10)
            | (self.taus_dm == 11)
        )
        # GenMatch = 0 or 6 = unmatched or jet, 1 or 3 = electron, 2 or 4 = muon, 5 = real tau
        tau_genMatch_mask = self.taus_genMatch == 5
        in_tau_mask = tau_dm_mask & tau_genMatch_mask
        # get 'in-limits' taus
        in_limit_taus = self.taus.mask[in_tau_mask]
        # get pt and eta
        # fill Nones with some 'in-limit' value
        tau_pt = ak.fill_none(in_limit_taus.pt, 0)
        tau_dm = ak.fill_none(in_limit_taus.decayMode, 0)
        tau_genMatch = ak.fill_none(in_limit_taus.genPartFlav, 0.0)

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset["DeepTau2017v2p1VSjet"].evaluate(
                tau_pt,
                tau_dm,
                tau_genMatch,
                self.wp_map[self.tau_vs_jet],
                self.wp_map[self.tau_vs_ele],
                "default",
                flag,
            ),
            in_tau_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSjet"].evaluate(
                    tau_pt,
                    tau_dm,
                    tau_genMatch,
                    self.wp_map[self.tau_vs_jet],
                    self.wp_map[self.tau_vs_ele],
                    "up",
                    flag,
                ),
                in_tau_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["DeepTau2017v2p1VSjet"].evaluate(
                    tau_pt,
                    tau_dm,
                    tau_genMatch,
                    self.wp_map[self.tau_vs_jet],
                    self.wp_map[self.tau_vs_ele],
                    "down",
                    flag,
                ),
                in_tau_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSjet_{self.year_key}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"CMS_eff_tau_idDeepTauVSjet_{self.year_key}",
                weight=nominal_sf,
            )
        return nominal_sf

        # By default, use the pT-dependent SFs with the 'pt' flag

    # pt = [24.59953, inf); dm = -1, 0, 1, 10; trigtype = 'ditau', 'etau', 'mutau', 'ditauvbf; wp "DeepTauVSjet"= Loose, Medium, Tight, VLoose, VTight, VVLoose, VVTight, VVVLoose; corrtype =  eff_data, eff_mc, sf;  syst = down, nom, up

    def add_id_weight_diTauTrigger(
        self, mask_trigger, trigger: str = "ditau", info: str = "sf", dm: int = -1
    ):
        """
            Tau Trigger SFs and efficiencies for {0} ditau, etau, mutau or ditauvbf triggers. Ditauvbf
        trigger SF is only available for 2017 and 2018. To get the usual DM-specific SF's, specify the
        DM, otherwise set DM to -1 to get the inclusive SFs. Default corrections are set to SF's, if you
        require the input efficiencies, you can specify so in the corrtype input variable

        """
        # tau pt range: [24.59953, inf]
        tau_pt_mask = self.taus_pt >= 40
        # tau decayMode
        tau_dm_mask = (
            (self.taus_dm == -1)
            | (self.taus_dm == 0)
            | (self.taus_dm == 1)
            | (self.taus_dm == 10)
        )
        tau_mask = tau_pt_mask & tau_dm_mask
        # get 'in-limits' taus
        in_limit_taus = self.taus.mask[tau_mask]
        # get pt and dm
        # fill Nones with some 'in-limit' value
        tau_pt = ak.fill_none(in_limit_taus.pt, 40.0)
        tau_dm = ak.fill_none(in_limit_taus.decayMode, -1)
        trigtype = trigger
        corrtype = info

        # get nominal scale factors
        sf = unflat_sf(
            self.cset["tau_trigger"].evaluate(
                tau_pt, tau_dm, trigtype, self.wp_map[self.tau_vs_jet], corrtype, "nom"
            ),
            tau_mask,
            self.n,
        )
        nominal_sf = np.where(mask_trigger, sf, 1.0)
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["tau_trigger"].evaluate(
                    tau_pt,
                    tau_dm,
                    trigtype,
                    self.wp_map[self.tau_vs_jet],
                    corrtype,
                    "up",
                ),
                tau_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["tau_trigger"].evaluate(
                    tau_pt,
                    tau_dm,
                    trigtype,
                    self.wp_map[self.tau_vs_jet],
                    corrtype,
                    "down",
                ),
                tau_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"CMS_eff_t_trigger_{self.year_key}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"CMS_eff_t_trigger_{self.year_key}",
                weight=nominal_sf,
            )
        return nominal_sf
