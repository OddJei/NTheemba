import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the API helper that's used by clients
const mockAPI = vi.fn();
vi.mock('./api', () => ({
  default: (path: string, opts: any) => mockAPI(path, opts),
}));

import * as clients from './clients';

beforeEach(() => {
  mockAPI.mockReset();
});

describe('clients wrappers', () => {
  it('msmeOnboard calls /msme/onboard and returns data', async () => {
    const sample = { business: { id: 'b1' }, user: { id: 'u1' }, msme_code: 'MSME123' };
    mockAPI.mockResolvedValueOnce(sample);

    const payload = {
      profile: { fullName: 'Test' },
      business: { businessName: 'T' },
    } as unknown as clients.MSMEOnboardRequest;

    const resp = await clients.msmeOnboard(payload);
    expect(mockAPI).toHaveBeenCalledWith('/msme/onboard', { method: 'POST', body: payload });
    expect(resp).toEqual(sample);
  });

  it('authLogin calls /auth/login and returns tokens + user', async () => {
    const sample = { accessToken: 'a', refreshToken: 'r', user: { id: 'u2', fullName: 'Bob' } };
    mockAPI.mockResolvedValueOnce(sample);

    const payload = { phone: '+260', password: 'pw' } as unknown as clients.AuthLoginReq;
    const resp = await clients.authLogin(payload);

    expect(mockAPI).toHaveBeenCalledWith('/auth/login', { method: 'POST', body: payload });
    expect(resp).toEqual(sample);
  });
});
