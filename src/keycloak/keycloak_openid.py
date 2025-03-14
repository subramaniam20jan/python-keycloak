# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (C) 2017 Marcos Pereira <marcospereira.mpj@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Keycloak OpenID module.

The module contains mainly the implementation of KeycloakOpenID class, the main
class to handle authentication and token manipulation.
"""

import json

from jose import jwt

from .authorization import Authorization
from .connection import ConnectionManager
from .exceptions import (
    KeycloakAuthenticationError,
    KeycloakAuthorizationConfigError,
    KeycloakDeprecationError,
    KeycloakGetError,
    KeycloakInvalidTokenError,
    KeycloakPostError,
    KeycloakRPTNotFound,
    raise_error_from_response,
)
from .uma_permissions import AuthStatus, build_permission_param
from .urls_patterns import (
    URL_AUTH,
    URL_CERTS,
    URL_ENTITLEMENT,
    URL_INTROSPECT,
    URL_LOGOUT,
    URL_REALM,
    URL_TOKEN,
    URL_USERINFO,
    URL_WELL_KNOWN,
)


class KeycloakOpenID:
    """Keycloak OpenID client.

    :param server_url: Keycloak server url
    :param client_id: client id
    :param realm_name: realm name
    :param client_secret_key: client secret key
    :param verify: True if want check connection SSL
    :param custom_headers: dict of custom header to pass to each HTML request
    :param proxies: dict of proxies to sent the request by.
    :param timeout: connection timeout in seconds
    """

    def __init__(
        self,
        server_url,
        realm_name,
        client_id,
        client_secret_key=None,
        verify=True,
        custom_headers=None,
        proxies=None,
        timeout=60,
    ):
        """Init method."""
        self.client_id = client_id
        self.client_secret_key = client_secret_key
        self.realm_name = realm_name
        headers = custom_headers if custom_headers is not None else dict()
        self.connection = ConnectionManager(
            base_url=server_url, headers=headers, timeout=timeout, verify=verify, proxies=proxies
        )

        self.authorization = Authorization()

    @property
    def client_id(self):
        """Get client id."""
        return self._client_id

    @client_id.setter
    def client_id(self, value):
        self._client_id = value

    @property
    def client_secret_key(self):
        """Get the client secret key."""
        return self._client_secret_key

    @client_secret_key.setter
    def client_secret_key(self, value):
        self._client_secret_key = value

    @property
    def realm_name(self):
        """Get the realm name."""
        return self._realm_name

    @realm_name.setter
    def realm_name(self, value):
        self._realm_name = value

    @property
    def connection(self):
        """Get connection."""
        return self._connection

    @connection.setter
    def connection(self, value):
        self._connection = value

    @property
    def authorization(self):
        """Get authorization."""
        return self._authorization

    @authorization.setter
    def authorization(self, value):
        self._authorization = value

    def _add_secret_key(self, payload):
        """Add secret key if exists.

        :param payload:
        :return:
        """
        if self.client_secret_key:
            payload.update({"client_secret": self.client_secret_key})

        return payload

    def _build_name_role(self, role):
        """Build name of a role.

        :param role:
        :return:
        """
        return self.client_id + "/" + role

    def _token_info(self, token, method_token_info, **kwargs):
        """Getter for the token data.

        :param token:
        :param method_token_info:
        :param kwargs:
        :return:
        """
        if method_token_info == "introspect":
            token_info = self.introspect(token)
        else:
            token_info = self.decode_token(token, **kwargs)

        return token_info

    def well_known(self):
        """Get the well_known object.

        The most important endpoint to understand is the well-known configuration
        endpoint. It lists endpoints and other configuration options relevant to
        the OpenID Connect implementation in Keycloak.

        :return It lists endpoints and other configuration options relevant.
        """
        params_path = {"realm-name": self.realm_name}
        data_raw = self.connection.raw_get(URL_WELL_KNOWN.format(**params_path))
        return raise_error_from_response(data_raw, KeycloakGetError)

    def auth_url(self, redirect_uri, scope="email", state=""):
        """Get authorization URL endpoint.

        :param redirect_uri: Redirect url to receive oauth code
        :type redirect_uri: str
        :param scope: Scope of authorization request, split with the blank space
        :type: scope: str
        :param state: State will be returned to the redirect_uri
        :type: str
        :returns: Authorization URL Full Build
        :rtype: str
        """
        params_path = {
            "authorization-endpoint": self.well_known()["authorization_endpoint"],
            "client-id": self.client_id,
            "redirect-uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
        return URL_AUTH.format(**params_path)

    def token(
        self,
        username="",
        password="",
        grant_type=["password"],
        code="",
        redirect_uri="",
        totp=None,
        **extra
    ):
        """Retrieve user token.

        The token endpoint is used to obtain tokens. Tokens can either be obtained by
        exchanging an authorization code or by supplying credentials directly depending on
        what flow is used. The token endpoint is also used to obtain new access tokens
        when they expire.

        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint

        :param username:
        :param password:
        :param grant_type:
        :param code:
        :param redirect_uri:
        :param totp:
        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "username": username,
            "password": password,
            "client_id": self.client_id,
            "grant_type": grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if extra:
            payload.update(extra)

        if totp:
            payload["totp"] = totp

        payload = self._add_secret_key(payload)
        data_raw = self.connection.raw_post(URL_TOKEN.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError)

    def refresh_token(self, refresh_token, grant_type=["refresh_token"]):
        """Refresh the user token.

        The token endpoint is used to obtain tokens. Tokens can either be obtained by
        exchanging an authorization code or by supplying credentials directly depending on
        what flow is used. The token endpoint is also used to obtain new access tokens
        when they expire.

        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint

        :param refresh_token:
        :param grant_type:
        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "client_id": self.client_id,
            "grant_type": grant_type,
            "refresh_token": refresh_token,
        }
        payload = self._add_secret_key(payload)
        data_raw = self.connection.raw_post(URL_TOKEN.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError)

    def exchange_token(
        self,
        token: str,
        client_id: str,
        audience: str,
        subject: str,
        requested_token_type: str = "urn:ietf:params:oauth:token-type:refresh_token",
        scope: str = "",
    ) -> dict:
        """Exchange user token.

        Use a token to obtain an entirely different token. See
        https://www.keycloak.org/docs/latest/securing_apps/index.html#_token-exchange

        :param token:
        :param client_id:
        :param audience:
        :param subject:
        :param requested_token_type:
        :param scope:
        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {
            "grant_type": ["urn:ietf:params:oauth:grant-type:token-exchange"],
            "client_id": client_id,
            "subject_token": token,
            "requested_token_type": requested_token_type,
            "audience": audience,
            "requested_subject": subject,
            "scope": scope,
        }
        payload = self._add_secret_key(payload)
        data_raw = self.connection.raw_post(URL_TOKEN.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError)

    def userinfo(self, token):
        """Get the user info object.

        The userinfo endpoint returns standard claims about the authenticated user,
        and is protected by a bearer token.

        http://openid.net/specs/openid-connect-core-1_0.html#UserInfo

        :param token:
        :return:
        """
        self.connection.add_param_headers("Authorization", "Bearer " + token)
        params_path = {"realm-name": self.realm_name}
        data_raw = self.connection.raw_get(URL_USERINFO.format(**params_path))
        return raise_error_from_response(data_raw, KeycloakGetError)

    def logout(self, refresh_token):
        """Log out the authenticated user.

        :param refresh_token:
        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {"client_id": self.client_id, "refresh_token": refresh_token}
        payload = self._add_secret_key(payload)
        data_raw = self.connection.raw_post(URL_LOGOUT.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError, expected_codes=[204])

    def certs(self):
        """Get certificates.

        The certificate endpoint returns the public keys enabled by the realm, encoded as a
        JSON Web Key (JWK). Depending on the realm settings there can be one or more keys enabled
        for verifying tokens.

        https://tools.ietf.org/html/rfc7517

        :return:
        """
        params_path = {"realm-name": self.realm_name}
        data_raw = self.connection.raw_get(URL_CERTS.format(**params_path))
        return raise_error_from_response(data_raw, KeycloakGetError)

    def public_key(self):
        """Retrieve the public key.

        The public key is exposed by the realm page directly.

        :return:
        """
        params_path = {"realm-name": self.realm_name}
        data_raw = self.connection.raw_get(URL_REALM.format(**params_path))
        return raise_error_from_response(data_raw, KeycloakGetError)["public_key"]

    def entitlement(self, token, resource_server_id):
        """Get entitlements from the token.

        Client applications can use a specific endpoint to obtain a special security token
        called a requesting party token (RPT). This token consists of all the entitlements
        (or permissions) for a user as a result of the evaluation of the permissions and
        authorization policies associated with the resources being requested. With an RPT,
        client applications can gain access to protected resources at the resource server.

        :return:
        """
        self.connection.add_param_headers("Authorization", "Bearer " + token)
        params_path = {"realm-name": self.realm_name, "resource-server-id": resource_server_id}
        data_raw = self.connection.raw_get(URL_ENTITLEMENT.format(**params_path))

        if data_raw.status_code == 404:
            return raise_error_from_response(data_raw, KeycloakDeprecationError)

        return raise_error_from_response(data_raw, KeycloakGetError)  # pragma: no cover

    def introspect(self, token, rpt=None, token_type_hint=None):
        """Introspect the user token.

        The introspection endpoint is used to retrieve the active state of a token.
        It is can only be invoked by confidential clients.

        https://tools.ietf.org/html/rfc7662

        :param token:
        :param rpt:
        :param token_type_hint:

        :return:
        """
        params_path = {"realm-name": self.realm_name}
        payload = {"client_id": self.client_id, "token": token}

        if token_type_hint == "requesting_party_token":
            if rpt:
                payload.update({"token": rpt, "token_type_hint": token_type_hint})
                self.connection.add_param_headers("Authorization", "Bearer " + token)
            else:
                raise KeycloakRPTNotFound("Can't found RPT.")

        payload = self._add_secret_key(payload)

        data_raw = self.connection.raw_post(URL_INTROSPECT.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError)

    def decode_token(self, token, key, algorithms=["RS256"], **kwargs):
        """Decode user token.

        A JSON Web Key (JWK) is a JavaScript Object Notation (JSON) data
        structure that represents a cryptographic key.  This specification
        also defines a JWK Set JSON data structure that represents a set of
        JWKs.  Cryptographic algorithms and identifiers for use with this
        specification are described in the separate JSON Web Algorithms (JWA)
        specification and IANA registries established by that specification.

        https://tools.ietf.org/html/rfc7517

        :param token:
        :param key:
        :param algorithms:
        :return:
        """
        return jwt.decode(token, key, algorithms=algorithms, audience=self.client_id, **kwargs)

    def load_authorization_config(self, path):
        """Load Keycloak settings (authorization).

        :param path: settings file (json)
        :return:
        """
        with open(path, "r") as fp:
            authorization_json = json.load(fp)

        self.authorization.load_config(authorization_json)

    def get_policies(self, token, method_token_info="introspect", **kwargs):
        """Get policies by user token.

        :param token: user token
        :return: policies list
        """
        if not self.authorization.policies:
            raise KeycloakAuthorizationConfigError(
                "Keycloak settings not found. Load Authorization Keycloak settings."
            )

        token_info = self._token_info(token, method_token_info, **kwargs)

        if method_token_info == "introspect" and not token_info["active"]:
            raise KeycloakInvalidTokenError("Token expired or invalid.")

        user_resources = token_info["resource_access"].get(self.client_id)

        if not user_resources:
            return None

        policies = []

        for policy_name, policy in self.authorization.policies.items():
            for role in user_resources["roles"]:
                if self._build_name_role(role) in policy.roles:
                    policies.append(policy)

        return list(set(policies))

    def get_permissions(self, token, method_token_info="introspect", **kwargs):
        """Get permission by user token.

        :param token: user token
        :param method_token_info: Decode token method
        :param kwargs: parameters for decode
        :return: permissions list
        """
        if not self.authorization.policies:
            raise KeycloakAuthorizationConfigError(
                "Keycloak settings not found. Load Authorization Keycloak settings."
            )

        token_info = self._token_info(token, method_token_info, **kwargs)

        if method_token_info == "introspect" and not token_info["active"]:
            raise KeycloakInvalidTokenError("Token expired or invalid.")

        user_resources = token_info["resource_access"].get(self.client_id)

        if not user_resources:
            return None

        permissions = []

        for policy_name, policy in self.authorization.policies.items():
            for role in user_resources["roles"]:
                if self._build_name_role(role) in policy.roles:
                    permissions += policy.permissions

        return list(set(permissions))

    def uma_permissions(self, token, permissions=""):
        """Get UMA permissions by user token with requested permissions.

        The token endpoint is used to retrieve UMA permissions from Keycloak. It can only be
        invoked by confidential clients.

        http://openid.net/specs/openid-connect-core-1_0.html#TokenEndpoint

        :param token: user token
        :param permissions: list of uma permissions list(resource:scope) requested by the user
        :return: permissions list
        """
        permission = build_permission_param(permissions)

        params_path = {"realm-name": self.realm_name}
        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
            "permission": permission,
            "response_mode": "permissions",
            "audience": self.client_id,
        }

        self.connection.add_param_headers("Authorization", "Bearer " + token)
        data_raw = self.connection.raw_post(URL_TOKEN.format(**params_path), data=payload)
        return raise_error_from_response(data_raw, KeycloakPostError)

    def has_uma_access(self, token, permissions):
        """Determine whether user has uma permissions with specified user token.

        :param token: user token
        :param permissions: list of uma permissions (resource:scope)
        :return: auth status
        """
        needed = build_permission_param(permissions)
        try:
            granted = self.uma_permissions(token, permissions)
        except (KeycloakPostError, KeycloakAuthenticationError) as e:
            if e.response_code == 403:  # pragma: no cover
                return AuthStatus(
                    is_logged_in=True, is_authorized=False, missing_permissions=needed
                )
            elif e.response_code == 401:
                return AuthStatus(
                    is_logged_in=False, is_authorized=False, missing_permissions=needed
                )
            raise

        for resource_struct in granted:
            resource = resource_struct["rsname"]
            scopes = resource_struct.get("scopes", None)
            if not scopes:
                needed.discard(resource)
                continue
            for scope in scopes:  # pragma: no cover
                needed.discard("{}#{}".format(resource, scope))

        return AuthStatus(
            is_logged_in=True, is_authorized=len(needed) == 0, missing_permissions=needed
        )
