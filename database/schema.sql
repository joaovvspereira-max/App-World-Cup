-- Esquema da base de dados para o Mundial 2026
-- Executa este script no SQL Editor do Supabase

-- Tabela de utilizadores (estende a auth do Supabase)
CREATE TABLE perfis (
    id uuid REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY,
    username TEXT UNIQUE,
    pontos_totais INTEGER DEFAULT 0
);

-- Tabela de jogos reais
CREATE TABLE jogos (
    id SERIAL PRIMARY KEY,
    equipa_casa TEXT,
    equipa_fora TEXT,
    golos_casa_real INT DEFAULT NULL,
    golos_fora_real INT DEFAULT NULL,
    fase TEXT,
    data DATE,
    grupo TEXT,
    cidade TEXT
);

-- Tabela de palpites dos utilizadores
CREATE TABLE palpites (
    id SERIAL PRIMARY KEY,
    utilizador_id uuid REFERENCES perfis(id),
    jogo_id INT REFERENCES jogos(id),
    golos_casa_palpite INT,
    golos_fora_palpite INT,
    UNIQUE (utilizador_id, jogo_id)
);

-- Dados de exemplo (opcional)
INSERT INTO jogos (equipa_casa, equipa_fora, fase, data, grupo, cidade) VALUES
    ('Portugal', 'Brasil', 'Grupos', '2026-06-15', 'H', 'Los Angeles'),
    ('Espanha', 'França', 'Grupos', '2026-06-16', 'A', 'Nova Iorque'),
    ('Alemanha', 'Argentina', 'Grupos', '2026-06-17', 'B', 'Dallas');
