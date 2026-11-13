# Ejecutar en Google Colab (Entorno de ejecucion -> Cambiar tipo -> GPU T4)
# Instala dependencias:
# !pip install "unsloth[colab-new] @ git+[https://github.com/unslothai/unsloth.git](https://github.com/unslothai/unsloth.git)"
# !pip install --no-deps xformers trl peft accelerate bitsandbytes

from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# 1. Cargar arquitectura base en 4-bit para modificar sus pesos
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-Coder-1.5B-Instruct",
    max_seq_length=2048,
    load_in_4bit=True,
)

# 2. Inyectar matrices entrenables LoRA (modifica las capas de atencion y MLP)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
)

# 3. Dataset propio de JARO 1.0 (amplia esta lista con tus propios ejemplos)
datos_jaro = [
    {
        "instruction": "Quien eres y cual es tu funcion?",
        "output": "Soy JARO 1.0, un nucleo de inteligencia artificial local desarrollado por Johan Restrepo para ingenieria de software, auditoria tecnica, vision artificial e investigacion web."
    },
    {
        "instruction": "Explica que es la complejidad algoritmica O(1).",
        "output": "La complejidad O(1) o tiempo constante significa que el tiempo de ejecucion de un algoritmo no depende del tamano de los datos de entrada, como ocurre al acceder a un indice directo de un arreglo o una tabla hash."
    }
]

def formatear(ejemplos):
    textos = []
    for inst, out in zip(ejemplos["instruction"], ejemplos["output"]):
        t = f"<|im_start|>system\nEres JARO 1.0, un sistema de IA independiente.<|im_end|>\n<|im_start|>user\n{inst}<|im_end|>\n<|im_start|>assistant\n{out}<|im_end|>"
        textos.append(t)
    return {"text": textos}

dataset = Dataset.from_list(datos_jaro).map(formatear, batched=True)

# 4. Entrenar y fusionar los nuevos pesos
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        max_steps=60,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        output_dir="jaro_weights",
    ),
)
trainer.train()

# 5. Exportar modelo fusionado independiente en formato GGUF cuantizado (Q4_K_M)
model.save_pretrained_gguf("jaro_1_0_gguf", tokenizer, quantization_method="q4_k_m")
print("Archivo jaro-1.0-unsloth.Q4_K_M.gguf generado con exito.")
