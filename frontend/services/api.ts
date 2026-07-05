export const mockLogin = async (email: string, password: string) => {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 1500))

  if (email === 'demo@flowzint.com' && password === 'password') {
    return {
      token: 'mock-jwt-token-xyz-123',
      user: {
        id: 'user-001',
        name: 'Demo Admin',
        email: 'demo@flowzint.com',
        role: 'admin',
      },
    }
  }

  throw new Error('Invalid credentials. Use demo@flowzint.com / password')
}
