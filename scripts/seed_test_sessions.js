use('test_database');
const exp = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
const users = [
  { user_id: 'test_customer', email: 'customer.test@example.com', name: 'Customer Uji', role: 'customer', token: 'test_session_customer' },
  { user_id: 'test_customer2', email: 'customer2.test@example.com', name: 'Customer Uji Dua', role: 'customer', token: 'test_session_customer2' },
  { user_id: 'test_photographer', email: 'naya.test@example.com', name: 'Naya Visuals', role: 'photographer', photographer_id: 'ph_01', bank_account_masked: '••••7890', token: 'test_session_photographer' },
  { user_id: 'test_admin', email: 'admin.test@example.com', name: 'Admin Uji', role: 'admin', token: 'test_session_admin' },
];
users.forEach(u => {
  const { token, ...doc } = u;
  db.users.updateOne({ user_id: u.user_id }, { $set: { ...doc, created_at: new Date().toISOString() } }, { upsert: true });
  db.user_sessions.deleteMany({ user_id: u.user_id });
  db.user_sessions.insertOne({ user_id: u.user_id, session_token: token, expires_at: exp, created_at: new Date().toISOString() });
});
db.photographers.updateOne({ photographer_id: 'ph_01' }, { $set: { user_id: 'test_photographer' } });
print('ok');
