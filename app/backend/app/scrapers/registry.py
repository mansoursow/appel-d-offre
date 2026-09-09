"""
Registre des scrapers ACTIFS. Pour brancher une nouvelle source :
  1. Creer app/scrapers/<mon_site>.py avec une classe heritant de BaseScraper
  2. L'importer et l'ajouter a ACTIVE_SCRAPERS ci-dessous
  3. Passer son "status" a "active" dans app/config.py (SOURCES)
Rien d'autre n'a besoin d'etre modifie : l'API, la base de donnees et le
frontend decouvrent automatiquement la nouvelle source.
"""
from .undp import UndpScraper
from .worldbank import WorldBankScraper
from .senoffre import SenOffreScraper
from .malipages import MalipagesScraper
from .linkedin import LinkedInGoogleScraper
from .marchespublics_ci import MarchesPublicsCIScraper
from .arcop_ci import ArcopCIScraper
from .dgmp_mali import DgmpMaliScraper
from .boad import BoadScraper
from .isdb import IsdbScraper
from .bceao import BceaoScraper
from .marchespublics_sn import MarchesPublicsSNScraper
from .lesoleil import LeSoleilScraper
from .marchesdusenegal import MarchesDuSenegalScraper
from .adepme import AdepmeScraper
from .j360 import J360Scraper
from .ungm import UngmScraper
from .ted import TedScraper
from .dgmarket import DgMarketScraper
from .luxdev import LuxDevScraper
from .expertise_france import ExpertiseFranceScraper
from .giz import GizScraper
from .aics_dakar import AicsDakarScraper
from .benin import BeninScraper

ACTIVE_SCRAPERS = [
    UndpScraper(),
    WorldBankScraper(),
    SenOffreScraper(),
    MalipagesScraper(),
    LinkedInGoogleScraper(),
    MarchesPublicsCIScraper(),
    ArcopCIScraper(),
    DgmpMaliScraper(),
    BoadScraper(),
    IsdbScraper(),
    BceaoScraper(),
    MarchesPublicsSNScraper(),
    LeSoleilScraper(),
    MarchesDuSenegalScraper(),
    AdepmeScraper(),
    J360Scraper(),
    UngmScraper(),
    TedScraper(),
    DgMarketScraper(),
    LuxDevScraper(),
    ExpertiseFranceScraper(),
    GizScraper(),
    AicsDakarScraper(),
    BeninScraper(),
]

ACTIVE_SCRAPERS_BY_ID = {s.source_id: s for s in ACTIVE_SCRAPERS}
