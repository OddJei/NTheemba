import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Scale, ShieldCheck, FileText, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function Terms() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            className="touch-target"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex items-center gap-2">
            <Scale className="w-6 h-6 text-blue-600" />
            <h1 className="text-xl font-bold text-gray-900">Terms & Conditions</h1>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="mb-6">
          <p className="text-sm text-gray-600">Last updated: February 20, 2026</p>
        </div>

        <div className="space-y-6">
          {/* Introduction */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                Introduction
              </CardTitle>
            </CardHeader>
            <CardContent className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed">
                Welcome to NTheemba! These Terms and Conditions ("Terms") govern your use of our
                platform and services. By accessing or using NTheemba, you agree to be bound by
                these Terms. Please read them carefully.
              </p>
            </CardContent>
          </Card>

          {/* Account Registration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-600" />
                1. Account Registration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold mb-2">1.1 Eligibility</h3>
                <p className="leading-relaxed">
                  You must be at least 18 years old to register an account on NTheemba. By
                  registering, you represent and warrant that you meet this age requirement.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">1.2 Account Information</h3>
                <p className="leading-relaxed">
                  You agree to provide accurate, current, and complete information during the
                  registration process and to update such information to keep it accurate, current,
                  and complete.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">1.3 Account Security</h3>
                <p className="leading-relaxed">
                  You are responsible for maintaining the confidentiality of your account
                  credentials and for all activities that occur under your account.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Platform Services */}
          <Card>
            <CardHeader>
              <CardTitle>2. Platform Services</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold mb-2">2.1 MSME Services</h3>
                <p className="leading-relaxed">
                  NTheemba provides a platform for Micro, Small, and Medium Enterprises (MSMEs) to
                  list and sell their products. MSMEs are responsible for the accuracy of product
                  listings, pricing, and fulfillment of orders.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">2.2 Affiliate Services</h3>
                <p className="leading-relaxed">
                  Affiliates can promote MSME products and earn commissions on successful sales.
                  Commission rates and payment terms are defined separately in the Affiliate
                  Program Agreement.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">2.3 Customer Services</h3>
                <p className="leading-relaxed">
                  Customers can browse, purchase, and review products listed on the platform.
                  Transactions are subject to product availability and seller confirmation.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Payments and Fees */}
          <Card>
            <CardHeader>
              <CardTitle>3. Payments and Fees</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold mb-2">3.1 Transaction Fees</h3>
                <p className="leading-relaxed">
                  NTheemba may charge transaction fees for sales processed through the platform.
                  Fee structures are communicated to MSMEs during onboarding.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">3.2 Payment Processing</h3>
                <p className="leading-relaxed">
                  All payments are processed securely through our payment partners. We do not store
                  complete payment card information on our servers.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">3.3 Refunds and Disputes</h3>
                <p className="leading-relaxed">
                  Refund policies are determined by individual sellers. In case of disputes,
                  NTheemba may mediate but is not liable for transaction outcomes.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* User Conduct */}
          <Card>
            <CardHeader>
              <CardTitle>4. User Conduct</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">You agree not to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Violate any applicable laws or regulations</li>
                <li>Infringe on intellectual property rights of others</li>
                <li>Post false, misleading, or fraudulent listings</li>
                <li>Engage in harassment or abusive behavior</li>
                <li>Attempt to circumvent platform security measures</li>
                <li>Use automated systems to access the platform without permission</li>
              </ul>
            </CardContent>
          </Card>

          {/* Intellectual Property */}
          <Card>
            <CardHeader>
              <CardTitle>5. Intellectual Property</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">
                The NTheemba platform, including its design, logos, and content, is protected by
                intellectual property laws. You may not copy, modify, or distribute our content
                without prior written permission.
              </p>
            </CardContent>
          </Card>

          {/* Limitation of Liability */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-600" />
                6. Limitation of Liability
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">
                NTheemba is provided "as is" without warranties of any kind. We are not liable for
                indirect, incidental, consequential, or punitive damages arising from your use of
                the platform.
              </p>
              <p className="leading-relaxed">
                Our total liability to you for any claims related to the platform shall not exceed
                the amount you paid to NTheemba in the past 12 months.
              </p>
            </CardContent>
          </Card>

          {/* Termination */}
          <Card>
            <CardHeader>
              <CardTitle>7. Termination</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">
                We reserve the right to suspend or terminate your account if you violate these
                Terms or engage in activities that harm the platform or other users. You may also
                terminate your account at any time by contacting support.
              </p>
            </CardContent>
          </Card>

          {/* Governing Law */}
          <Card>
            <CardHeader>
              <CardTitle>8. Governing Law</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">
                These Terms are governed by the laws of Zambia. Any disputes arising from these
                Terms shall be resolved in the courts of Zambia.
              </p>
            </CardContent>
          </Card>

          {/* Changes to Terms */}
          <Card>
            <CardHeader>
              <CardTitle>9. Changes to These Terms</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p className="leading-relaxed">
                We may update these Terms from time to time. We will notify you of any changes by
                posting the new Terms on this page and updating the "Last updated" date. Your
                continued use of the platform after changes constitutes acceptance of the new
                Terms.
              </p>
            </CardContent>
          </Card>

          {/* Contact */}
          <Card>
            <CardHeader>
              <CardTitle>10. Contact Information</CardTitle>
            </CardHeader>
            <CardContent className="text-gray-700">
              <p className="leading-relaxed mb-4">
                If you have any questions about these Terms, please contact us:
              </p>
              <div className="space-y-2 text-sm">
                <p>
                  <strong>Email:</strong>{' '}
                  <a href="mailto:legal@ntheemba.com" className="text-blue-600 hover:underline">
                    legal@ntheemba.com
                  </a>
                </p>
                <p>
                  <strong>Address:</strong> NTheemba Platform, Lusaka, Zambia
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Footer Actions */}
        <div className="mt-8 flex justify-center">
          <Button onClick={() => navigate(-1)} className="touch-target-large">
            I Understand
          </Button>
        </div>
      </main>
    </div>
  );
}
