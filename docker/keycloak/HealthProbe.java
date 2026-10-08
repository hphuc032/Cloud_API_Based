// Verified HTTPS readiness for Keycloak's minimal production image (no curl).
import java.io.FileInputStream;
import java.net.URI;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;

class HealthProbe {
    public static void main(String[] args) throws Exception {
        var certificates = CertificateFactory.getInstance("X.509");
        var store = KeyStore.getInstance(KeyStore.getDefaultType());
        store.load(null, null);
        try (var stream = new FileInputStream("/run/tls/identity-ca.pem")) {
            int i = 0;
            for (var cert : certificates.generateCertificates(stream)) {
                store.setCertificateEntry("identity-" + i++, cert);
            }
        }
        var managers = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        managers.init(store);
        var context = SSLContext.getInstance("TLS");
        context.init(null, managers.getTrustManagers(), null);
        var connection = (HttpsURLConnection) URI.create("https://keycloak:9000/health/ready").toURL().openConnection();
        connection.setSSLSocketFactory(context.getSocketFactory());
        // Keep the JDK's default hostname verification enabled.
        connection.setConnectTimeout(3000);
        connection.setReadTimeout(3000);
        if (connection.getResponseCode() != 200) throw new IllegalStateException("Identity not ready");
        connection.disconnect();
    }
}
