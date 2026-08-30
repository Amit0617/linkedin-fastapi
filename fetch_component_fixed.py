import json
import argparse
import re
import os
from dotenv import load_dotenv
from curl_cffi import requests

load_dotenv()

def parse_vanity_name(url: str) -> str:
    match = re.search(r'linkedin\.com/in/([^/?#]+)', url)
    if not match:
        raise ValueError("Invalid LinkedIn profile URL")
    return match.group(1)

parser = argparse.ArgumentParser(description="Fetch LinkedIn profile components")
parser.add_argument("url", help="LinkedIn profile URL (e.g., https://linkedin.com/in/username)")
args = parser.parse_args()

VANITY_NAME = parse_vanity_name(args.url)

COOKIES = {
    "li_at": os.environ["LI_AT"],
    "JSESSIONID": os.environ["JSESSIONID"],
    "bcookie": os.environ["BCOOKIE"],
    "bscookie": os.environ["BSCOOKIE"],
    "lidc": os.environ["LIDC"],
}

HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://www.linkedin.com",
    "referer": f"https://www.linkedin.com/in/{VANITY_NAME}/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "x-li-rsc-stream": "true",
    "x-li-anchor-page-key": "d_flagship3_profile_view_base",
    "x-li-application-version": "0.2.7003",
    "x-li-track": json.dumps({
        "clientVersion": "0.2.7003",
        "mpVersion": "0.2.7003",
        "osName": "web",
        "timezoneOffset": 5.5,
        "timezone": "Asia/Kolkata",
        "deviceFormFactor": "DESKTOP",
        "mpName": "web",
        "displayDensity": 1,
        "displayWidth": 1920,
        "displayHeight": 1080
    }),
    "priority": "u=4",
    "te": "trailers",
}

PAYLOAD_TEMPLATE = {
    "clientArguments": {
        "payload": {
            "isSelfView": False,
            "vanityName": VANITY_NAME,
            "replaceableSectionArgs": {
                "vanityName": VANITY_NAME,
                "hideCardsForGoldenGate": False,
                "shouldSetupReplaceableComponent": True,
                "vieweeProfileId": "ACoAADO6xgIBCG2qNLR3KMd0DIY3js6R1Xy1fL8",
                "isSelfView": False,
                "isSelfViewResolved": False
            },
            "profileComponentState": {
                "profileId": VANITY_NAME,
                "shouldRefreshScreenOnReappear": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldRefreshScreen{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldFetchFromCache": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateFetchFromCache{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldDisplayTabAnchors": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldDisplayTabAnchors{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldReloadTopCardOnReappear": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldReloadTopCardOnReappear{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "deferredTopCardReloadProfileId": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateDeferredTopCardReloadProfileId{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldDisplayStickyHeader": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldDisplayStickyHeader{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldRefreshLanguageDetailScreen": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldRefreshLanguageDetails{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "lastPerformedActionRef": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateLastPerformedActionRef{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldFocusOnReappear": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldFocusOnReappear{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldFocusFeaturedOnReappear": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateShouldFocusFeaturedOnReappear{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "lastFeaturedActionRef": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateLastFeaturedActionRef{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                },
                "shouldHideProfileCards": {
                    "type": "com.linkedin.sdui.components.core.BindingImpl",
                    "value": {
                        "key": f"ProfileComponentStateProfileHideCards{VANITY_NAME}ProfileComponentState",
                        "namespace": "MemoryNamespace"
                    }
                }
            }
        },
        "states": [],
        "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
        "screenId": "com.linkedin.sdui.flagshipnav.profile.Profile",
        "knownTemplateIds": []
    }
}

COMPONENTS = [
    {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity",
        "parent_span_id": "7SQoGJ4JDn0=",
        "span_id_for_trace": "7b8d7cda71ad4b06",
    },
    {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsExperienceOnly",
        "parent_span_id": "zeJIHbF7p5Q=",
        "span_id_for_trace": "c6d3fb4ba60c292a",
    },
    {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart1WithoutExp",
        "parent_span_id": "c1DSFVXUfwo=",
        "span_id_for_trace": "9099d6b38b079fe3",
    },
]

PAGE_INSTANCE_TRACKING_ID = "Ua6G+jyrSuWSabC3yPMEzw=="
APPLICATION_INSTANCE = "UIemU9pyQqyllovzu/L7VA=="
PAGE_FOREST_ID = "00065a30ea39c2020018bdb1b5ed1622"
TRACE_ID = "00065a30ea39c2020018bdb1b5ed1622"

def fetch_component(comp):
    csrf_token = COOKIES["JSESSIONID"]
    
    headers = HEADERS.copy()
    headers.update({
        "csrf-token": csrf_token,
        "x-li-page-instance-tracking-id": PAGE_INSTANCE_TRACKING_ID,
        "x-li-application-instance": APPLICATION_INSTANCE,
        "x-li-page-instance": f"urn:li:page:d_flagship3_profile_view_base;{PAGE_INSTANCE_TRACKING_ID}",
        "x-li-traceparent": f"00-{TRACE_ID}-{comp['span_id_for_trace']}-00",
        "x-li-tracestate": f"LinkedIn={comp['span_id_for_trace']}",
        "x-li-pageforestid": PAGE_FOREST_ID,
    })
    
    url = "https://www.linkedin.com/flagship-web/rsc-action/actions/component"
    params = {
        "componentId": comp["component_id"],
        "sduiid": comp["component_id"],
        "parentSpanId": comp["parent_span_id"]
    }
    
    response = requests.post(
        url,
        headers=headers,
        cookies=COOKIES,
        json=PAYLOAD_TEMPLATE,
        params=params,
        impersonate="firefox133"
    )
    
    print(f"[{comp['component_id'].split('.')[-1]}] Status: {response.status_code}")
    if response.status_code == 200:
        filename = f"component_{comp['component_id'].split('.')[-1]}.json"
        with open(filename, "w") as f:
            f.write(response.content.decode("utf-8", errors="ignore"))
        print(f"  Saved: {filename}")
    else:
        print(f"  Error: {response.text[:300]}")
    
    return response

if __name__ == "__main__":
    for comp in COMPONENTS:
        fetch_component(comp)