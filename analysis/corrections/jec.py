import gzip
import cloudpickle
import numpy as np
import awkward as ak
import importlib.resources
from typing import Tuple
from coffea.nanoevents.methods.base import NanoEventsArray


# Recomendations https://twiki.cern.ch/twiki/bin/viewauth/CMS/JECDataMC#Recommended_for_MC
def apply_jet_corrections(events: NanoEventsArray, year: str) -> None:
    """
    Apply JEC/JER corrections to jets (propagate to MET)

    We use the script data/scripts/build_jec.py to create the 'mc_jec_compiled.pkl.gz'
    file with jet and MET factories

    Parameters:
    -----------
        events:
            events collection
        year:
            Year of the dataset {'2016preVFP', '2016postVFP', '2017', '2018'}
    """
    if hasattr(events, "genWeight"):
        # load jet and MET factories with JEC/JER corrections
        with importlib.resources.path(
            "analysis.data", "mc_jec_compiled.pkl.gz"
        ) as path:
            with gzip.open(path) as fin:
                factories = cloudpickle.load(fin)

        def add_jec_variables(jets: ak.Array, event_rho: ak.Array):
            """add some variables to the jet collection"""
            jets["pt_raw"] = (1 - jets.rawFactor) * jets.pt
            jets["mass_raw"] = (1 - jets.rawFactor) * jets.mass
            jets["pt_gen"] = ak.values_astype(
                ak.fill_none(jets.matched_gen.pt, 0), np.float32
            )
            jets["event_rho"] = ak.broadcast_arrays(event_rho, jets.pt)[0]
            return jets

        # get corrected jets
        events["Jet"] = factories["jet_factory"][year].build(
            add_jec_variables(events.Jet, events.fixedGridRhoFastjetAll),
            events.caches[0],
        )

        # get corrected MET
        events["MET"] = factories["met_factory"].build(events.MET, events.Jet, {})
