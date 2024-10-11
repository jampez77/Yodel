"""Constants for the Royal Mail integration."""

DOMAIN = "yodel"
HOST = "https://www.yodel.co.uk/graphql"
CONF_VARIABLES = "variables"
CONF_MFA_CODE = "mfa_code"
CONF_MOBILE = "mobile"
CONF_DEVICE_FINGERPRINT = "device_fingerprint"
CONF_POST = "POST"
CONF_YODEL_DEVICE_ID = "x-yodel-device-id"
CONF_REFRESH_TOKEN = "x-refresh-token"
CONF_DEVICEID = "deviceId"
CONF_TOKEN = "token"
CONF_REFRESHTOKEN = "refreshToken"
CONF_ACTIVE = "active"
CONF_AUTHORIZATION = "Authorization"
CONF_ERRORS = "errors"
CONF_MESSAGE = "message"
CONF_DATA = "data"
CONF_CAPTUREMOBILE = "captureMobile"
CONF_VERIFYAPPMOBILENUMBER = "verifyAppMobileNumber"
CONF_YODELPARCEL = "yodelParcel"
CONF_UPICODE = "upiCode"
CONF_STATUSMESSAGE = "statusMessage"
CONF_ACCESSTOKEN = "accessToken"
CONF_PARCELS = "parcels"
CONF_USER = "user"
CONF_EMAIL = "email"
CONF_OUT_FOR_DELIVERY = "out_for_delivery"
CONF_NICKNAME = "nickname"
CONF_UPI_CODE = "upi_code"
CONF_UPICODE = "upiCode"
CONF_TRACK_A_PARCEL = "track_a_parcel"
CONF_NAME_A_PARCEL = "name_a_parcel"
CONF_POSTCODE = "postcode"
CONF_CONSIGNMENTORUPICODE = "consignmentOrUpiCode"
CONF_TRACKPARCEL = "trackParcel"
CONF_QUERY = "query"
CONF_TRACKINGEVENTS = "trackingEvents"
CONF_SCAN_CODE = "scan_code"
CONF_SCAN_DESCRIPTION = "scan_description"
PARCEL_DELIVERED = ["ZA"]
PARCEL_DELIVERY_TODAY = ["ET"]
PARCEL_IN_TRANSIT = ["A", "QI", "PJ", "1", "BH"]

REQUEST_HEADER_API_KEY = {
    "apiKey": "RGVplG9He66OnnAjnGKz7Ovol9dKbSAr",
    "Content-Type": "application/json",
}

REQUEST_HEADER = {
    "Content-Type": "application/json",
    CONF_AUTHORIZATION: "{bearer_token}",
    CONF_YODEL_DEVICE_ID: "{deviceId}",
    CONF_REFRESH_TOKEN: "{refreshToken}",
}


CAPTURE_MOBILE_POST_BODY = {
    CONF_QUERY: """
        mutation ($mobile: String!, $deviceId: String!) {
            captureMobile(mobile: $mobile, deviceId: $deviceId) {
                errors
                __typename
            }
        }
    """,
    CONF_VARIABLES: {CONF_MOBILE: "{mobile}", CONF_DEVICEID: "{deviceId}"},
}

VERIFY_MOBILE_POST_BODY = {
    CONF_QUERY: """
        mutation ($token: String!, $deviceId: String!) {
          verifyAppMobileNumber(token: $token, deviceId: $deviceId) {
            deviceId
            accessToken {
                token
                refreshToken
                __typename
            }
            user {
                id
                email
                firstname
                surname
                active
                mobile
                yodelTermsOfService
                addressWizard
                __typename
            }
            __typename
            }
        }
    """,
    CONF_VARIABLES: {CONF_TOKEN: "{token}", CONF_DEVICEID: "{deviceId}"},
}


TRACK_PARCEL_POST_BODY = {
    CONF_QUERY: """
        query trackParcel($consignmentOrUpiCode: String!, $postcode: String) {
        trackParcel(consignmentOrUpiCode: $consignmentOrUpiCode, postcode: $postcode) {
            isAdvice
            isAdviceTypeR
            isAdviceTypeSSentToHome
            isAdviceTypeSSentToStore
            isReturn
            isYodelParcel
            collectionCodeMessage
            customerTrackingParcelsResponse
            displayState
            state
            deliveredAt
            deliveredParcelStrapline
            deliveredNeighbourLocation
            deliveredSafePlaceLocation
            trackingTitle
            trackingEvents
            origin {
            __typename
            ... on YodelParcel {
                upiCode
                clientName
                currentStatusId
                edd
                neighbourInfo
                nickname
                safePlaceInfo
                state
                statusInfo
                statusMessage
                cdyParcel
                parcelType
                __typename
            }
            ... on Return {
                upiCode
                address
                brandName
                cancelled
                consignment
                guid
                labelUrl
                price
                printInStore
                reasonCode {
                id
                reason
                __typename
                }
                refundable
                retailerReference
                retailerReferenceLabel
                returnReference
                returnReferenceLabel
                state
                __typename
            }
            ... on Advice {
                upiCode
                state
                barcodeUrl
                brandName
                collectable
                consignment
                receivingStore {
                address
                city
                closed
                closingMessage
                detailedOpeningHours
                id
                lat
                lng
                name
                postcode
                staticmapImageThumbUrl
                __typename
                }
                __typename
            }
            }
            yodelParcel {
            upiCode
            clientName
            currentStatusId
            edd
            neighbourInfo
            nickname
            safePlaceInfo
            state
            statusInfo
            statusMessage
            cdyParcel
            parcelType
            source
            __typename
            }
            __typename
        }
        }
    """,
    CONF_VARIABLES: {
        CONF_CONSIGNMENTORUPICODE: "{consignmentOrUpiCode}",
        CONF_POSTCODE: "{postcode}",
    },
}

PARCELS_POST_BODY = {
    CONF_QUERY: """
        query ($active: Boolean) {
            parcels(active: $active) {
                isAdvice
                isAdviceTypeR
                isAdviceTypeSSentToHome
                isAdviceTypeSSentToStore
                isReturn
                isYodelParcel
                state
                displayState
                trackingTitle
                origin {
                    __typename
                    ... on Return {
                        upiCode
                        address
                        brandName
                        cancelled
                        consignment
                        guid
                        labelUrl
                        price
                        printInStore
                        reasonCodeLabel
                        reasonCode {
                            id
                            reason
                            __typename
                        }
                        refundable
                        retailerReference
                        retailerReferenceLabel
                        returnReference
                        returnReferenceLabel
                        state
                        returnDeductionAmount
                        __typename
                    }
                    ... on Advice {
                        upiCode
                        state
                        barcodeUrl
                        brandName
                        collectable
                        consignment
                        __typename
                    }
                }
                yodelParcel {
                    upiCode
                    clientName
                    currentStatusId
                    edd
                    neighbourInfo
                    nickname
                    safePlaceInfo
                    state
                    statusInfo
                    source
                    statusMessage
                    cdyParcel
                    parcelType
                    completedAt
                    matchedAt
                    reasonForPreferenceNotAppliedString
                    postcode
                    userId
                    __typename
                }
                __typename
            }
        }
    """,
    CONF_VARIABLES: {CONF_ACTIVE: True},
}

NAME_PARCEL_POST_BODY = {
    CONF_QUERY: """
        mutation ($upiCode: String!, $nickname: String!) {
            updateYodelParcel(upiCode: $upiCode, nickname: $nickname) {
                parcel {
                    upiCode
                    nickname
                    __typename
                }
                __typename
            }
        }
    """,
    CONF_VARIABLES: {CONF_UPICODE: "{upiCode}", CONF_NICKNAME: "{nickname}"},
}
