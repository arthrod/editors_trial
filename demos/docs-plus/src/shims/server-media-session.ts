/**
 * Browser stand-in for the server's media-session module.
 *
 * The conversion domain only reads the media route path, to decide whether a
 * cookie may travel with an export image request. The static demo has no
 * private media route and no cookies, so the constant is the only thing kept.
 */
export const MEDIA_SESSION_COOKIE = 'dp_media'
export const MEDIA_SESSION_TTL_S = 3600
export const MEDIA_SESSION_PATH = '/api/plugins/hypermultimedia'
