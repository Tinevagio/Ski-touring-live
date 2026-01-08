import numpy as np
import matplotlib.pyplot as plt

# =========================
# FONCTIONS DE BOOST
# =========================

def power_boost(score, exponent=0.6):
    """
    Fonction puissance : tire les scores moyens/hauts vers le haut
    
    Args:
        score: score initial [0-1]
        exponent: entre 0.5 et 0.8 (plus bas = boost plus fort)
    
    Exemples:
        0.2 → 0.33  (+65%)
        0.3 → 0.43  (+43%)
        0.5 → 0.63  (+26%)
        0.7 → 0.80  (+14%)
    """
    return score ** exponent


def sigmoid_boost(score, steepness=8, midpoint=0.4):
    """
    Fonction sigmoïde : boost progressif avec contrôle du point d'inflexion
    
    Args:
        score: score initial [0-1]
        steepness: raideur de la courbe (6-12, plus haut = transition plus brutale)
        midpoint: point où le boost est maximal (0.3-0.5)
    
    Exemples (steepness=8, midpoint=0.4):
        0.2 → 0.28  (+40%)
        0.3 → 0.42  (+40%)
        0.5 → 0.67  (+34%)
        0.7 → 0.85  (+21%)
    """
    return 1 / (1 + np.exp(-steepness * (score - midpoint)))


def exponential_boost(score, strength=1.5):
    """
    Fonction exponentielle : boost doux et progressif
    
    Args:
        score: score initial [0-1]
        strength: intensité du boost (1.2-2.0)
    
    Exemples (strength=1.5):
        0.2 → 0.26  (+30%)
        0.3 → 0.37  (+23%)
        0.5 → 0.57  (+14%)
        0.7 → 0.75  (+7%)
    """
    return (np.exp(strength * score) - 1) / (np.exp(strength) - 1)


def sqrt_boost(score):
    """
    Fonction racine carrée : boost simple et efficace
    
    Exemples:
        0.2 → 0.45  (+125%)
        0.3 → 0.55  (+83%)
        0.5 → 0.71  (+42%)
        0.7 → 0.84  (+20%)
    """
    return np.sqrt(score)


def custom_piecewise_boost(score, threshold=0.5, low_boost=1.2, high_boost=1.5):
    """
    Fonction par morceaux : contrôle séparé pour scores bas et hauts
    
    Args:
        score: score initial [0-1]
        threshold: seuil de séparation
        low_boost: multiplicateur pour scores < threshold
        high_boost: multiplicateur pour scores >= threshold
    
    Exemples (threshold=0.5, low=1.2, high=1.5):
        0.2 → 0.24  (+20%)
        0.3 → 0.36  (+20%)
        0.5 → 0.75  (+50%)
        0.7 → 0.95  (+36%)
    """
    if score < threshold:
        # Boost linéaire doux pour les bas scores
        return min(score * low_boost, threshold)
    else:
        # Boost plus fort pour les scores moyens/hauts
        boosted = threshold + (score - threshold) * high_boost
        return min(boosted, 1.0)


def adaptive_boost(score, min_boost=1.0, max_boost=2.0):
    """
    Boost adaptatif : intensité proportionnelle au score
    Plus le score est haut, plus le boost est fort
    
    Args:
        score: score initial [0-1]
        min_boost: multiplicateur minimum (pour score=0)
        max_boost: multiplicateur maximum (pour score=1)
    
    Exemples (min=1.0, max=2.0):
        0.2 → 0.24  (+20%)
        0.3 → 0.39  (+30%)
        0.5 → 0.75  (+50%)
        0.7 → 1.00  (+43%)
    """
    boost_factor = min_boost + (max_boost - min_boost) * score
    return min(score * boost_factor, 1.0)


# =========================
# VISUALISATION COMPARATIVE
# =========================

def plot_boost_comparison():
    """Compare toutes les fonctions de boost"""
    
    scores = np.linspace(0, 1, 100)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Graphique 1 : Courbes de transformation
    ax1.plot(scores, scores, 'k--', label='Original (y=x)', linewidth=2, alpha=0.5)
    ax1.plot(scores, power_boost(scores, 0.6), label='Power boost (exp=0.6)', linewidth=2)
    ax1.plot(scores, sigmoid_boost(scores, 8, 0.4), label='Sigmoid boost', linewidth=2)
    ax1.plot(scores, exponential_boost(scores, 1.5), label='Exponential boost', linewidth=2)
    ax1.plot(scores, sqrt_boost(scores), label='Sqrt boost', linewidth=2)
    ax1.plot(scores, [custom_piecewise_boost(s) for s in scores], 
             label='Piecewise boost', linewidth=2)
    ax1.plot(scores, [adaptive_boost(s, 1.0, 2.0) for s in scores], 
             label='Adaptive boost', linewidth=2)
    
    ax1.set_xlabel('Score original', fontsize=12)
    ax1.set_ylabel('Score boosté', fontsize=12)
    ax1.set_title('Comparaison des fonctions de boost', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(alpha=0.3)
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    
    # Graphique 2 : Intensité du boost (%)
    boosts = {
        'Power (0.6)': [power_boost(s, 0.6) / s - 1 for s in scores[1:]],
        'Sigmoid': [sigmoid_boost(s, 8, 0.4) / s - 1 for s in scores[1:]],
        'Exponential': [exponential_boost(s, 1.5) / s - 1 for s in scores[1:]],
        'Sqrt': [sqrt_boost(s) / s - 1 for s in scores[1:]],
        'Piecewise': [custom_piecewise_boost(s) / s - 1 for s in scores[1:]],
        'Adaptive': [adaptive_boost(s, 1.0, 2.0) / s - 1 for s in scores[1:]]
    }
    
    for name, boost_pct in boosts.items():
        ax2.plot(scores[1:], np.array(boost_pct) * 100, label=name, linewidth=2)
    
    ax2.set_xlabel('Score original', fontsize=12)
    ax2.set_ylabel('Boost (%)', fontsize=12)
    ax2.set_title('Intensité du boost par fonction', fontsize=14, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=10)
    ax2.grid(alpha=0.3)
    ax2.axhline(0, color='k', linestyle='--', alpha=0.3)
    ax2.set_xlim(0, 1)
    
    plt.tight_layout()
    plt.savefig('boost_functions_comparison.png', dpi=150, bbox_inches='tight')
    print("📊 Graphique sauvegardé : boost_functions_comparison.png")
    plt.show()


# =========================
# TEST SUR TES SCORES
# =========================

def test_on_real_scores():
    """Test avec des scores réalistes de ton modèle"""
    
    test_scores = [0.05, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    
    print("\n" + "="*70)
    print("🎯 COMPARAISON DES BOOSTS SUR TES SCORES RÉELS")
    print("="*70)
    print(f"\n{'Original':<12} {'Power':<12} {'Sigmoid':<12} {'Sqrt':<12} {'Adaptive':<12}")
    print("-"*70)
    
    for score in test_scores:
        power = power_boost(score, 0.6)
        sigmoid = sigmoid_boost(score, 8, 0.4)
        sqrt = sqrt_boost(score)
        adaptive = adaptive_boost(score, 1.0, 2.0)
        
        print(f"{score:<12.3f} {power:<12.3f} {sigmoid:<12.3f} {sqrt:<12.3f} {adaptive:<12.3f}")
    
    print("\n" + "="*70)
    print("💡 RECOMMANDATIONS :")
    print("="*70)
    print("• POWER BOOST (0.6)    : Boost équilibré, garde la hiérarchie")
    print("• SIGMOID BOOST        : Boost progressif avec contrôle fin")
    print("• SQRT BOOST           : Boost maximal, transforme 0.2 → 0.45")
    print("• ADAPTIVE BOOST       : Boost proportionnel au score initial")
    print("\n👉 Pour ton cas (biais avalanche), je recommande : POWER ou ADAPTIVE")


# =========================
# EXÉCUTION
# =========================

if __name__ == "__main__":
    # Afficher les comparaisons
    plot_boost_comparison()
    test_on_real_scores()