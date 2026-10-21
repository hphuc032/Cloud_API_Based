"""Fail-closed deployment bounds; pure settings validation without a database."""
import secrets
import pytest
from pydantic import ValidationError
from app.config import Settings


def candidate(**overrides):
 values={'DATABASE_URL':'postgresql://unused@postgres/p0_baseline','AUTH_MODE':'legacy',
         'SECRET_KEY':secrets.token_hex(32),'WEBHOOK_SECRET':secrets.token_hex(32),
         'WEBHOOK_PREVIOUS_SECRET':None,'WEBHOOK_PREVIOUS_START':0,'WEBHOOK_PREVIOUS_UNTIL':0}
 values.update(overrides)
 return Settings(_env_file=None,**values)

@pytest.mark.parametrize('case',['short-old-key','same-key','empty-interval','backwards','over-900','anchors-without-key',
 'negative-tolerance','over-900-tolerance','small-body','huge-body','invalid-provider'])
def test_unsafe_webhook_configuration_rejected(case):
 current=secrets.token_hex(32);old=secrets.token_hex(32)
 changes={'WEBHOOK_SECRET':current,'WEBHOOK_PREVIOUS_SECRET':old,'WEBHOOK_PREVIOUS_START':100,'WEBHOOK_PREVIOUS_UNTIL':1000}
 if case=='short-old-key':changes['WEBHOOK_PREVIOUS_SECRET']='too-short'
 elif case=='same-key':changes['WEBHOOK_PREVIOUS_SECRET']=current
 elif case=='empty-interval':changes['WEBHOOK_PREVIOUS_UNTIL']=100
 elif case=='backwards':changes['WEBHOOK_PREVIOUS_UNTIL']=99
 elif case=='over-900':changes['WEBHOOK_PREVIOUS_UNTIL']=1001
 elif case=='anchors-without-key':changes['WEBHOOK_PREVIOUS_SECRET']=None
 elif case=='negative-tolerance':changes['WEBHOOK_TIMESTAMP_TOLERANCE']=-1
 elif case=='over-900-tolerance':changes['WEBHOOK_TIMESTAMP_TOLERANCE']=901
 elif case=='small-body':changes['WEBHOOK_MAX_BODY_BYTES']=1023
 elif case=='huge-body':changes['WEBHOOK_MAX_BODY_BYTES']=1048577
 elif case=='invalid-provider':changes['WEBHOOK_PROVIDER']='untrusted/provider'
 with pytest.raises(ValidationError):candidate(**changes)


def test_explicit_maximum_overlap_and_body_bound_are_supported():
 s=candidate(WEBHOOK_PREVIOUS_SECRET=secrets.token_hex(32),WEBHOOK_PREVIOUS_START=100,WEBHOOK_PREVIOUS_UNTIL=1000,
             WEBHOOK_TIMESTAMP_TOLERANCE=900,WEBHOOK_MAX_BODY_BYTES=1048576)
 assert s.WEBHOOK_PREVIOUS_UNTIL-s.WEBHOOK_PREVIOUS_START==900
 assert candidate().WEBHOOK_PREVIOUS_SECRET is None
