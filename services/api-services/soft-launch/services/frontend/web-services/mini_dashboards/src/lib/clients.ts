import API from './api';

// Auth
export interface AuthRegisterReq {
  fullName: string;
  email: string;
  phone: string;
  password?: string;
}

export interface AuthLoginReq {
  phone?: string;
  email?: string;
  password: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface UserMe {
  id: string;
  fullName: string;
  email?: string;
  phone?: string;
}

export async function authRegister(payload: AuthRegisterReq): Promise<UserMe> {
  return API('/auth/register', { method: 'POST', body: payload });
}

export async function authLogin(payload: AuthLoginReq): Promise<AuthTokens & { user: UserMe }> {
  return API('/auth/login', { method: 'POST', body: payload });
}

export async function authRefresh(refreshToken: string): Promise<AuthTokens> {
  return API('/auth/refresh', { method: 'POST', body: { refreshToken } });
}

export async function authLogout(): Promise<void> {
  return API('/auth/logout', { method: 'POST' });
}

export async function getMe(): Promise<UserMe> {
  return API('/auth/me', { method: 'GET' });
}

// Onboarding
export interface OnboardProfile {
  fullName: string;
  email?: string;
  phone?: string;
  location?: string;
}

export interface OnboardBusiness {
  businessName: string;
  businessType?: string;
  description?: string;
  yearsInBusiness?: string;
}

export interface OnboardProduct {
  name: string;
  category?: string;
  price?: string;
  initialStock?: string;
}

export interface MSMEOnboardRequest {
  profile: OnboardProfile;
  business: OnboardBusiness;
  products?: OnboardProduct[];
}

export interface MSMEOnboardResponse {
  business: any;
  user: any;
  msme_code?: string;
}

export async function msmeOnboard(payload: MSMEOnboardRequest): Promise<MSMEOnboardResponse> {
  return API('/msme/onboard', { method: 'POST', body: payload });
}

export interface AffiliatePreferences {
  categories?: string[];
  commissionPreference?: string;
  bio?: string;
}

export interface AffiliateOnboardRequest {
  profile: OnboardProfile;
  preferences?: AffiliatePreferences;
}

export interface AffiliateOnboardResponse {
  user: any;
  affiliate_id?: string;
}

export async function affiliateOnboard(payload: AffiliateOnboardRequest): Promise<AffiliateOnboardResponse> {
  return API('/affiliate/onboard', { method: 'POST', body: payload });
}

export interface CustomerOnboardRequest {
  profile: OnboardProfile;
  termsAccepted: boolean;
}

export interface CustomerOnboardResponse {
  user: any;
  customer_id?: string;
}

export async function customerOnboard(payload: CustomerOnboardRequest): Promise<CustomerOnboardResponse> {
  return API('/customer/onboard', { method: 'POST', body: payload });
}

// Business
export interface BusinessRegisterReq {
  name: string;
  owner_id: string;
}

export async function registerBusiness(payload: BusinessRegisterReq): Promise<any> {
  return API('/business/register', { method: 'POST', body: payload });
}

export async function getBusiness(id: string): Promise<any> {
  return API(`/business/${id}`, { method: 'GET' });
}

// Notifications
export async function getNotificationsForUser(userId: string): Promise<any[]> {
  return API(`/notification/user/${userId}`, { method: 'GET' });
}

export async function sendNotification(payload: unknown): Promise<any> {
  return API('/notification/send', { method: 'POST', body: payload });
}

export default {
  authRegister,
  authLogin,
  authRefresh,
  authLogout,
  getMe,
  msmeOnboard,
  affiliateOnboard,
  customerOnboard,
  registerBusiness,
  getBusiness,
  getNotificationsForUser,
  sendNotification,
};
