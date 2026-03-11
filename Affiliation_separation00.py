import requests
import json
import re  # Added for robust JSON parsing


def parse_affiliation_with_ollama(raw_affiliation_string, model_name="qwen3:4b"):
    """
    Connects to a local Ollama instance to parse a raw affiliation string
    into Company, Address, and Country, returning a JSON structure.

    Args:
        raw_affiliation_string (str): The raw string of a single affiliation.
        model_name (str): The name of the model downloaded via Ollama.

    Returns:
        dict or str: The parsed affiliation as a Python dictionary, or an error message.
    """
    # Ollama's default API endpoint for generating responses
    OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

    # --- 1. System Prompt (Defines the Rules) ---
    SYSTEM_PROMPT = (
        """
        You are an expert data parsing and structuring assistant. Your sole task is to analyze a list of raw academic or corporate affiliation strings and strictly separate it into three distinct components: 'Company', 'Address', and 'Country'. But be quick and concise.
    
        RULES:
        1.  **Company (Institution/Corporation):** This must be the main name of the entity (e.g., 'Massachusetts Institute of Technology', 'Department of Chemistry', 'Fraunhofer ISE'). But This can contain subsidiary names if they are part of the official name, like the department within a university.
        2.  **Country:** This must be the official or common name of the country (e.g., 'Germany', 'USA', 'China').
        3.  **Address:** This is everything else, typically the street address, city, state, and postal/zip code.
        4.  **Output Format:** You MUST return the result as a single JSON object. Do not include any text, explanations, or quotes outside of the JSON object.
        """
    )

    # --- 2. User Prompt (The Request Template) ---
    USER_PROMPT_TEMPLATE = """
    Please process the following list of raw affiliation strings and return the result in the specified JSON format.

    RAW AFFILIATION STRING:
    "{raw_affiliation_string}"

    REQUIRED JSON FORMAT:
    {{[
      "Company": "...",
      "Address": "...",
      "Country": "..."],[...],...}}
    """

    # --- 3. Construct the full prompt for the API ---
    full_prompt = USER_PROMPT_TEMPLATE.format(raw_affiliation_string=raw_affiliation_string)

    payload = {
        "model": model_name,
        "prompt": full_prompt,  # Use the correctly formatted user prompt
        "system": SYSTEM_PROMPT,
        "stream": True,
        "options": {
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()

        # The raw response text (which should be a JSON string)
        json_string = data.get('response', 'Error: No response text found.')

        # Robustly extract only the JSON object, as LLMs sometimes add ```json delimiters
        match = re.search(r'\{.*\}', json_string, re.DOTALL)
        if match:
            clean_json_string = match.group(0)
            return json.loads(clean_json_string)
        else:
            return {"error": "Failed to extract JSON object from LLM response.", "raw_output": json_string}

    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to Ollama. Ensure Ollama is running and the model is loaded."}
    except requests.exceptions.RequestException as e:
        return {"error": f"An API request error occurred: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to decode JSON from LLM output: {e}", "raw_output": json_string}


# --- Example Usage ---
raw_affiliation_1 = "School of Electrical Engineering, University of New South Wales, Sydney, NSW, Australia"
raw_affiliation_2 = "Institut für Chemische Technologie, WACKER Chemie AG, Burghausen, Germany"
raw_affiliation_3 = """Faculty of Engineering Science, Chair of Chemical Engineering Universitätsstraße 30, D-95447 Bayreuth, Germany;
Technical University of Munich Catalysis Research Center and School of Natural Sciences Department of Chemistry Ernst-Otto-Fischer-Straße 1, D-85748 Garching bei München, Germany;
Leibniz  institute  for  catalysis,  Rostock;
DSM-Firmenich, Kaiseraugst/Switzerland;
dsm-firmenich AG, Wurmisweg 576, Kaiseraugst/CH;
Leibniz-Institut für Katalyse
Rostock/Gemany
Institute of Technical and Macromolecular Chemistry, Universität Hamburg, Bundesstraße 45, 20146 Hamburg, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
Ruhr University Bochum, Bochum;
Leibniz-Institut für Katalyse e.V. (LIKAT), Rostock, Germany;
Technische Universität Berlin, Berlin, Germany;
Institute for Sustainable and Circular Chemistry, Utrecht University, Utrecht, The Netherlands; TotalEnergies, Harfleur, France; TotalEnergies, Solaize, France
Evonik Oxeno GmbH, Marl/Germany; Ruhr-Universität Bochum, Bochum/Germany;University of Oslo, Oslo/Norway;
Hamburg University of Technology, 21073 Hamburg, Germany;
Karlsruhe Institute of Technology, 76128 Karlsruhe, Germany;
Reacnostics GmbH, 20457 Hamburg, Germany;
Clariant Produkte (Deutschland) GmbH, Heufeld / Munich, Germany;
KIT, Eggenstein-Leopoldshafen;
Ruhr University Bochum; Leipzig University; Evonik Operations GmbH;
Institute of Technical and Macromolecular Chemistry RWTH Aachen University, Aachen, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
Ruhr-Universität Bochum, Bochum/Germany;
Jakob Albert, Institute of Technical and Macromolecular Chemistry, University of Hamburg, Hamburg/Germany;
Technische Universität Berlin, Straße des 17. Juni 124, 10623 Berlin;
Technical University of Darmstadt, Darmstadt, Germany;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
Fritz Haber Institute of the Max Planck Society, Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
Institute of Chemical Engineering, Ulm University, Albert-Einstein-Allee 11, 89081 Ulm, Germany;
Department of Chemistry, Massachusetts Institute of Technology, Cambridge/USA; Technical University of Munich, Garching/Germany
Fritz-Haber Institut, Berlin, Germany;
BasCat – UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
ASF SE, Catalysis Research, Ludwigshafen, Germany
Interface Science Department, Fritz Haber Institute of the Max Planck Society, 14195 Berlin, Germany;
Institute of Polymer Chemistry, University of Stuttgart, Pfaffenwaldring 55, D-70569 Stuttgart, Germany;
2Institute of Organic Chemistry, University of Stuttgart, Pfaffenwaldring 55, D-70569 Stuttgart, Germany;
hte GmbH, Kurpfalzring 104, 69123 Heidelberg, Germany;
Institute for Integrated Catalysis and Physical Science Division, Pacific Northwest National Laboratory, Richland, Washington 99354, United States;
BASF SE, 67065 Ludwigshafen, Germany;
Department of Chemistry and Catalysis Research Institute, TU München, Lichtenbergstrasse 4, 85748 Garching, Germany;
Delft University of Technology, Delft; Kiel University, Kiel;
nstitute for Chemical Technology and Polymer Chemistry (ITCP), Karlsruhe Institute of Technology (KIT), 76131 Karlsruhe, Germany; Institute of Catalysis Research and Technology (IKFT), Karlsruhe Institute of Technology (KIT), 76344 Eggenstein-Leopoldshafen, Germany;
Siemens AG, Technology, Advanced Manufacturing & Circularity, 13629 Berlin/81739 Munich;
Interface Science Department, Fritz Haber Institute of the Max Planck Society, 14195 Berlin, Germany;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
BASF SE, Group Research, Ludwigshafen, Germany;
Eduard-Zintl-Institut für Anorganische und Physikalische Chemie, Technical University of Darmstadt, Germany;
Ruhr University Bochum, Bochum/Germany;
Fraunhofer Institute for Environmental Safety and Energy Technology UMSICHT, Oberhausen/Germany;
Shaanxi Normal University, Xi'an/China;
Leibniz Institute for Catalysis e.V. (LIKAT), Albert-Einstein-Street 29a, 18059 Rostock, Germany;
TU Darmstadt, Ernst-Berl-Institut, Darmstadt/Germany;
MilliporeSigma, Bellefonte/USA;
Friedrich-Alexander-Universität Erlangen-Nürnberg, Power-to-X Technologies, Fürth/Germany;
Merck Life Science KGaA, Darmstadt/Germany;
Verbio SE, Hannover, Germany;
all XiMo Hungary Kft, Budapest/Hungary;
Laboratory of Industrial Chemistry, Ruhr University Bochum, 44780 Bochum, Germany;
Chinese Academy of Science (CAS) Key Laboratory of Nanosystem and Hierarchy Fabrication, CAS Center for Excellence in Nanoscience, National Center for Nanoscience and Technology, P. R. China, Beijing 100190;
Competence Center Chase GmbH, Linz, Austria; Johannes Kepler University, Linz, Austria;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
TH Köln – Campus Leverkusen, Leverkusen, Germany;
Institute of Energy Process Engineering and Chemical Engineering, Chair of
Reaction Engineering, TU Bergakademie Freiberg, Germany;
TU Freiberg, Institute of Energy Process
Engineering and Chemical Engineering, Chair of Reaction Engineering, Freiberg,
Germany;
Institute of Inorganic Chemistry, RWTH Aachen University, Germany; Peter Grünberg Institut, Forschungszentrum Jülich GmbH, Germany
Friedrich Schiller University Jena, Institute for Technical Chemistry and Environmental Chemistry, Jena/Germany;
Helmholtz Institute for Polymers in Energy Applications Jena (HIPOLE Jena), Jena/Germany, Helmholtz-Zentrum Berlin für Materialien und Energie GmbH,Berlin/Germany;Martin Kolen, Davide Ripepi, Wilson A. Smith, Thomas Burdyny, and Fokko M. Mulder, ACS Catalysis 2022 12 (10); S. Chen, S. Perathoner, C. Ampelli, C. Mebrahtu, D. Su, G. Centi, Angew. Chem. Int. Ed. 2017, 56, 2699;
Lehrstuhl für Chemische Reaktionstechnik (CRT), Friedrich-Alexander-UniversitätErlangen-Nürnberg (FAU), Egerlandstr. 3, 91058 Erlangen, Germany.;
Helmholtz-Institut Erlangen-Nürnberg für Erneuerbare Energien (IEK-11), ForschungszentrumJülich, Egerlandstrasse 3, 91058 Erlangen, Germany.;
Institute of Catalysis Research and Technology, Karlsruhe Institute of Technology,Eggenstein-Leopoldshafen, Germany;
Department of Chemistry, Technical University of Denmark, Lyngby, Denmark;
Technical University Bergakademie
Freiberg, Freiberg, Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Straße 29a, 18059 Rostock, Germany;
Heraeus Precious Metals GmbH &
Co. KG, Hanau, Germany;
School of Science, Constructor University, Bremen;
Leibniz Institute for Catalysis, Rostock/Germany;
Kiel University, Germany;
Fraunhofer Institute for Environmental, Safety and Energy Technology UMSICHT, Oberhausen, Germany; Leuchtstoffwerke Breitungen GmbH, Breitungen/Werra, Germany;
Institute of Energy Process Engineering and Chemical Engineering, Chair of Reaction Engineering, Freiberg University of Technology, Freiberg/Germany;
Institute of Chemistry, Technical University Berlin, Straße des 17. Juni 124, 10623 Berlin;
Karlsruhe Institute of Technology, Karlsruhe/Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
TU Bergakademie Freiberg, Freiberg, Germany;
Laboratory of Industrial Chemistry, Ruhr University Bochum, 44780 Bochum, Germany;
Institute of Chemical Reaction Engineering, FAU, Erlangen, Germany;
Interface Research and Catalysis, ECRC, FAU, Erlangen, Germany;
Department Interface Design, HZB, Berlin, Germany;
Karlsruhe Institute of Technology, Institute for Inorganic Chemistry, Karlsruhe, Germany,;
BASF SE, Ludwigshafen, Germany;
hte GmbH, Heidelberg, Germany;
Brandenburgische Technische Universität Cottbus-Senftenberg, Cottbus/Germany; Universidad Autónoma de Madrid, Madrid/Spain; Institute of Catalysis and Petrochemistry (ICP), CSIC, Madrid/Spain;
BasCat – UniCat BASF JointLab, D-10623 Berlin (Germany); BASF SE, Group Research, D-67063 Ludwigshafen (Germany);
Forschungszentrum Jülich GmbH, HIERN, Erlangen, Germany;
Clariant AG, Bruckmühl, Germany;
TU Bergakademie Freiberg, Institut für Physikalische Chemie, Leipziger Str. 29, 09599 Freiberg, Germany;
Max Planck Institute for Dynamics of Complex Technical Systems, Department for Process Systems Engineering, Sandtorstraße 1, 39106 Magdeburg;
Otto von Guericke University Magdeburg, Lehrstuhl für Systemverfahrenstechnik, Universitätsplatz 2, 39106 Magdeburg;
Institute of Chemical Engineering, Ulm University, Ulm/Germany;
Technical University of Freiberg, Freiberg/Germany;
School of Science, Constructor University, Campus Ring 1, 28759 Bremen, Germany;
Leibniz-Institut für Katalyse e.V, Albert-Einstein-Straße 29a, Rostock, Germany;
State Key Laboratory of Low Carbon Catalysis and Carbon Dioxide Utilization, Lanzhou Institute of Chemical Physics, Chinese Academy of Sciences No.18, Tianshui Middle Road, Lanzhou, China;
Symrise AG, Mühlenfeldstraße 1, Holzminden, Germany;
Institute of Chemistry, Otto-von-Guericke University, Magdeburg, Germany;
Ruhr-Universität Bochum, Bochum/Germany; Fraunhofer UMSICHT, Oberhausen/Germany; Shaanxi Normal University,Xi’an/China;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr/Germany
BasCat – UniCat BASF Joint Lab, TU Berlin, Germany;
Department of Chemistry/Functional Materials, TU Berlin, Germany;
Department of Chemistry, Metalorganics and Inorganic Materials, TU Berlin, Germany;
Department of Chemistry, TU Berlin, Germany;
Institute of Biotechnology, TU Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
Karlsruhe Institute of Technology, Karlsruhe, Germany;
Institute of Chemical Reaction Engineering, FAU Erlangen-Nürnberg;
Helmholtz Institute Erlangen-Nürnberg for Renewable Energy (IEK-11);
Forschungszentrum Jülich GmbH, Institute for Sustainable Hydrogen Economy (INW), Jülich/Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany; Institut für Chemie, Technische Universität Berlin, Berlin, Germany;
Department of Interface Science, Fritz Haber Institute of the Max Planck Society, Faradayweg 4-6, 14195 Berlin, Germany;
DECHEMA e.V., Theodor-Heuss-Allee 25, 60486 Frankfurt a. M., Germany;
Technical University Berlin, Institute of Environmental Technology, Straße des 17. Juni 135, 10623 Berlin, Germany;
NanoCASE GmbH, Breitschachenstr. 12A, 9032 Engelburg, Switzerland
Helmholtz Centre of Environmental Research (UFZ), Department of Ecotoxicology, Permoserstrasse 15, 04318 Leipzig, Germany;
Karlsruhe Institute of Technology (KIT), Institute for Automation und Applied Informatics (IAI), Kaiserstr. 12, 76131 Karlsruhe, Germany;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
Inorganic Chemistry Department, Fritz-Haber-Institute of the Max-Planck-Society, Berlin, Germany;
Department of Chemistry, Functional Materials, Technische Universität Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
RWTH Aachen University, Aachen/Germany.;
KU Leuven, Leuven/Belgium.;
Forschungszentrum Jülich, Jülich/Germany.;
Friedrich-Alexander-Universität, Erlangen-Nürnberg / Germany; Ruđer Bošković Institute, Zagreb / Croatia;
TU-Darmstadt, Darmstadt/Germany;
Fraunhofer Institute for Chemical Technology, Pfinztal / Germany; Heidelberg University, Heidelberg / Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
Chair of Heterogeneous Catalysis and Technical Chemistry, Institute for Technical and Macromolecular Chemistry, RWTH Aachen University;
Institute for a Sustainable Hydrogen Economy, Forschungszentrum Jülich GmbH;
Karlsruhe Institute of Technology, Eggenstein-Leopoldshafen, Germany;
TU Dortmund University, Dortmund, Germany;
Universität Siegen, Siegen, Deutschland;
Karlsruhe Institute of Technology, Kalsruhe/Germany;
Hamburg University of Technology, 21073 Hamburg, Germany; Reacnostics GmbH, 20457 Hamburg, Germany Introduction;
Interface Research and Catalysis, FAU Erlangen-Nürnberg, Egerlandstraße 3, 91058 Erlangen, Germany;
Department of Chemistry and Pharmacy, FAU Erlangen-Nürnberg, Egerlandstraße 1, 91058 Erlangen, Germany;
Chemistry of Thin Film Materials, FAU Erlangen-Nürnberg, Cauerstraße 3, 91058 Erlangen, Germany;
Institute of Micro- and Nanostructure Research & Center for Nanoanalysis and Electron Microscopy, FAU Erlangen-Nürnberg, Cauerstraße 3, 91058 Erlangen, Germany;
Fraunhofer-Institute for Silicate Research ISC, Neunerplatz 2, D97082 Würzburg, Germany;
Interface Research and Catalysis, FAU, Erlangen, Germany;
Institute of Chemical Reaction Engineering, FAU, Erlangen, Germany;
Department of Chemical Engineering, University of Cape Town, South Africa;
Institute of Chemistry, Technische Universität
Berlin, Straße des 17. Juni 124, 10623 Berlin, Germany; BasCat – UniCat BASF JointLab, Technische Universität
Berlin, Straße des 17. Juni 124, 10623 Berlin, Germany;
Institute for a SustainableHydrogen Economy, Forschungszentrum Jülich GmbH, Jülich; 
Institute of Technical and Macromolecular Chemistry, RWTH Aachen University, Aachen, Germany.;
Laboratory of Industrial Chemistry, Ruhr University Bochum, Bochum, Germany;
Analytical Chemistry – CES, Ruhr University Bochum, Bochum, Germany;
IVG, Institute for Combustion and Gas Dynamics – Reactive Fluids, and CENIDE, Center for Nanointegration, University of Duisburg-Essen, Duisburg, Germany;
Institute for Inorganic Chemistry, University Duisburg-Essen, Germany;
Max-Planck-Institut für Kohlenforschung, Mülheim, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim, Germany;
Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim a.d. Ruhr, Germany;
Institute of Technical and Macromolecular Chemistry, RWTH Aachen University, Aachen, Germany;
ITQ Instituto de Tecnología Química (CSIC-UPV), Spain;
Friedrich Schiller University Jena, Institute for Technical Chemistry and Environmental Chemistry, Jena/Germany;
Helmholtz Institute for Polymers in Energy Applications Jena (HIPOLE Jena), Helmholtz-Zentrum Berlin für Materialien und Energie GmbH, Jena/Germany.;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
Surface Physics and Catalysis, Department of Physics, Technical University of Denmark, 2800 Kgs. Lyngby, Denmark.;
VISION, Department of Physics, Technical University of Denmark, 2800 Kgs. Lyngby, Denmark.;
National Centre for Nano Fabrication and Characterization (Nanolab), Technical University of Denmark, 2800 Kgs. Lyngby, Denmark.;
Laboratory of Industrial Chemistry, Department of Biochemical and Chemical Engineering, TU Dortmund University, Dortmund, Germany;
RWTH Aachen University, Aachen/GER; Forschungszentrum Jülich, Jülich/GER;
Institute for a SustainableHydrogen Economy, Forschungszentrum Jülich GmbH, Jülich;
Institute for Technical and Macromolecular Chemistry, RWTH Aachen University, Aachen, Germany;
Leibniz-Institut für Katalyse, Albert-Einstein-Straße 29a, Rostock 18059, Germany;
Max Planck-Cardiff Centre on the Fundamentals of Heterogeneous Catalysis FUNCAT, Translational Research Hub, Cardiff University, Maindy Road, Cardiff CF24 4HQ, UK;
Eduard-Zintl-Institut für Anorganische und Physikalische Chemie, Technical University of Darmstadt, 64287 Darmstadt, Germany;
Eduard-Zintl-Institute of Inorganic and Physical Chemistry Technical University of Darmstadt, Germany;
Competence Center Chase GmbH, Linz, Austria; Johannes Kepler University, Linz, Austria;
Friedrich-Alexander Universität Erlangen-Nürnberg, Fürth, Germany;
Norwegian University of Science and Technology, Trondheim, Norway;
Institute of Inorganic Chemistry (IAC), RWTH Aachen University, Landoltweg 1a, 52074 Aachen, Germany;
Hamburg University of Technology, 21073 Hamburg, Germany;
Deutsches Elektronen-Synchrotron DESY, 22607 Hamburg, Germany;
Karlsruhe Institute of Technology, 76131 Karlsruhe, Germany;
Reacnostics GmbH, 20457 Hamburg, Germany;
Interface Research and Catalysis, Erlangen Center for Interface Research and Catalysis, FAU, D-91058 Erlangen, Germany;
Department of Physics, Institute of Theoretical Physics, FAU, D-91058 Erlangen, Germany;
Department of Chemical and Biological Engineering, Particle Technology, FAU, D-91058 Erlangen, Germany;
Department of Chemical and Biological Engineering, Chemical Engineering I, FAU, D-91058 Erlangen, Germany;
Karlsruhe Institute of Technology, Eggenstein-Leopoldshafen/Germany;
University of Padova, Padova, Italy; Silvia Gross, University of Padova,Padova, Italy;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
hte GmbH, Heidelberg, Germany;
BASF SE, Group Research, Ludwigshafen, Germany;
BASF SE, Group Research, Ludwigshafen, Germany;
BasCat - UniCat BASF Joint Lab, Technische Universität Berlin, Germany;
hte GmbH, Heidelberg, Germany;
Institute of Chemical Technology, Universität Leipzig, Leipzig, Germany;
Fraunhofer FOKUS – Institute for Open Communication Systems, Berlin, Germany;
Heraeus Precious Metals GmbH & Co. KG, Hanau, Germany;
Eduard-Zintl-Institut für Anorganische und Physikalische Chemie, TU Darmstadt;
Paderborn University, Paderborn/Germany;
Fritz-Haber-Institut, Max-Planck-Gesellschaft, Berlin, Germany;
Max-Planck-Institut für Chemische Energiekonversion, Mülheim, Germany;
Humboldt-Universität zu Berlin, Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Fritz-Haber Institute of the Max Planck Society, 14195 Berlin, Germany;
Helmholtz-Zentrum Berlin für Materialien und Energie GmbH, 12489 Berlin, Germany;
TUM School of Natural Sciences, Department of Chemistry, Technical University of Munich, Garching/Germany; 
ASG Analytik-Service AG, Neusäss/Germany;
Faculty of Mechanical and Process Engineering, Technical University of Applied Sciences Augsburg, Augsburg/Germany; 
Technical University of Munich, Catalysis Research Center, Garching/Germany;
KIT, Institute of Catalysis Research and Technology, Eggenstein-Leopoldshafen, Karlsruhe, Germany;
KIT, Institute for Chemical Technology and Polymer Chemistry, Karlsruhe, Germany;
Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Lehrstuhl für Chemische Reaktionstechnik, Erlangen, Germany;
Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Lehrstuhl für Informatik 6 (Datenmanagement), Erlangen, Germany;
Istanbul Technical University, Istanbul/Turkey;
Technical University of Freiberg, Freiberg/Germany;
Karlsruhe Institute of Technology, Eggenstein-Leopoldshafen/Germany;
Institute for Chemical Technology and Polymer Chemistry, Karlsruhe Institute of Technology (KIT), Karlsruhe;
Institute for Chemical Technology and Polymer Chemistry, Karlsruhe Institute of Technology (KIT), Engesserstr. 20, Karlsruhe 76131, Germany;
Institute of Engineering Thermophysics, Chinese Academy of Sciences, Beijing 100190, China;
University of Chinese Academy of Sciences, Beijing 100049, China;
Institiute for Chemical Technology and Polymer Chemistry, Karlsruhe Institute of Technology, Karlsruhe, Germany;
Institute of Catalysis Research and Technology, Karlsruhe Institute of Technology, Eggenstein-Leopoldshafen, Germany;
Fraunhofer Institute for Chemical Technology ICT, Pfinztal/ Germany;
Brandenburg University of Technology, Cottbus-Senftenberg/ Germany;
Mannheim University of Applied Sciences, Mannheim/ Germany;
Catalysis Institute, University of Cape Town, South Africa;
Friedrich Schiller University Jena, Center for Energy and Environmental Chemistry Jena, Institute for Technical Chemistry and Environmental Chemistry, Philosophenweg 7a, 07743 Jena, Germany;
Institute of Inorganic Chemistry, RWTH Aachen University, Landoltweg 1a, 52074 Aachen, Germany;
The Fuel Science Center for Automotive Catalytic Systems Aachen, RWTH Aachen University, 52074 Aachen, Germany.;
MPI for Chemical Energy Conversion, Mülheim an der Ruhr, Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Technische Chemie II, Technische Universität Darmstadt, D-64289 Darmstadt.;
Center for Energy and Environmental Chemistry, Philosophenweg 7a Friedrich-Schiller-Universität, 07743 Jena/Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Avantium R&D Solutions, Amsterdam/ The Netherlands;
Christian-Albrechts-Universität zu Kiel, 24118 Kiel;
Fritz-Haber-Institut der Max-Planck Gesellschaft;
Henkel, AID/Digital Twins & Data Analytics;
University of Duisburg-Essen, 45141 Essen;
MPI for Chemical Energy Conversion, 45470 Mülheim;
Eduard-Zintl-Institut für Anorganische und Physikalische Chemie, Technische
Universität Darmstadt, Darmstadt, Deutschland;
Department of Chemistry and Pharmacy, Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Egerlandstraße 1, D91058 Erlangen, Germany;
Institute of Micro- and Nanostructure Research (IMN) & Center for Nanoanalysis and Electron Microscopy (CENEM), Interdisciplinary Center for Nanostructured Films (IZNF), Department of Materials Science and Engineering, Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Cauerstrasse 3, D91058 Erlangen, Germany;
Institute of Separation Science and Technology, Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Egerlandstraße 3, D91058 Erlangen, Germany;
INM – Leibniz-Institute for New Materials, Campus D2 2, 66123 Saarbrücken, Germany;
Interface Research and Catalysis, Erlangen Center for Interface Research and Catalysis (ECRC), Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Egerlandstraße 3, 91058 Erlangen, Germany;
Colloid and Interface Chemistry, Saarland University Campus D2 2, 66123 Saarbrücken, Germany;
Fraunhofer-Institute for Silicate Research ISC, Neunerplatz 2, D97082 Würzburg, Germany;
Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
Helmholtz-Zentrum Berlin für Materialien und Energie GmbH, Berlin, Germany;
Max-Planck-Institut für Chemische Energiekonversion, Mülheim an der Ruhr,Germany;
Energy Materials In-situ Laboratory Berlin (EMIL), HZB, Berlin, Germany;
Friedrich-Alexander-Universität Erlangen-Nürnberg, Erlangen, Germany;
Helmholtz-Institute Erlangen-Nürnberg for Renewable Energy, Berlin, Germany;
Microtrac Retsch GmbH, Haan, Germany;
Microtrac BEL, Osaka, Japan;
Max Planck Institute for Chemical Energy Conversion, Muelheim an der Ruhr, Germany.
Technical University of Munich, TUM School of Natural Sciences, Lichtenbergstr. 4, 85748 Garching near Munich, Germany;
Technical University of Munich, Catalysis Research Center, Ernst-Otto-Fischer-Straße 1, 85748 Garching near Munich, Germany;
Fraunhofer FOKUS – Institute for Open Communication Systems, Berlin, Germany;
BasCat - UniCat BASF Joint Lab, Technische Universität Berlin, Germany;
Fraunhofer Institute, Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
Technische Universität Berlin, Berlin, Germany;
Institute of Inorganic Chemistry, Christian-Albrechts-Universität zu Kiel, Germany;
Institute of Energy Process Engineering and Chemical Engineering, Chair of Reaction Engineering, TU Bergakademie Freiberg, Germany;
Heraeus Precious Metals GmbH & Co. KG, Hanau/Germany;
Leibniz-Institut für Katalyse e.V. (LIKAT) Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Institut für Chemie, Technische Universität Berlin, Berlin, Germany;
BasCat – UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
Interface Science Department, Fritz-Haber-Institut der MPG, Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
Max-Planck-Institut für Chemische Energiekonversion, Mülheim a.d. Ruhr, Germany;
Otto-von-Guericke-Universität Magdeburg, Magdeburg, Germany;
RWTH Aachen, Aachen, Germany;
Catalysis Institute, University of Cape Town, Cape Town, South Africa;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
BASF SE, Catalysis Research, Ludwigshafen, Germany;
Max Planck Institute of Colloids and Interfaces, Potsdam, Germany;
Leibniz Institute for Catalysis e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
EPFL Lausanne, Lausanne, Switzerland;
Forschungszentrum Jülich GmbH, Jülich, Germany;
Helmholtz-Zentrum Berlin, Berlin, Germany;
Deutsches GeoForschungsZentrum GFZ, Potsdam, Germany;
Institute for Catalysis Research & Technology, Karlsruhe Institute of Technology, 76344 Eggenstein-Leopoldshafen, Germany;
Department of Process and Plant Technology, Brandenburg University of Technology Cottbus-Senftenberg, Cottbus;
Programa de Pós-Graduação em Energia e Ambiente (PGENAM), Escola Politécnica, Universidade Federal da Bahia, Salvador, Brazil;
Leibniz-Institut für Katalyse e.V., Rostock/Germany;
Centre for Materials Science and Nanotechnology (SMN), University of Oslo, Norway;
Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
Helmholtz-Zentrum Berlin für Materialien und Energie GmbH: PVcomB;
Max-Planck-Institut für Chemische Physik fester Stoffe, Dresden, Germany;
Department of Process and Plant Technology, Brandenburg University of Technology Cottbus-Senftenberg, Cottbus, Germany.;
Department of Chemical & Life Science Engineering, College of Engineering, Virginia;
Humboldt Universität zu Berlin, Berlin/Germany; 
Helmholtz-Zentrum, Berlin/Germany;
Fritz-Haber-Institut, Berlin/Germany;
University of São Paulo, São Paulo/Brazil;
Karlsruhe Institute of Technology, Karlsruhe/Germany;
Department of Inorganic Chemistry, Fritz-Haber Institute of the Max Planck Society, 14195, Berlin, Germany;
PVcomB, Helmholtz-Zentrum Berlin für Materialien und Energie GmbH, 12489 Berlin, Germany;
Theory Department, Fritz-Haber Institute of the Max Planck Society, 14195, Berlin, Germany;
Helmholtz-Zentrum Berlin für Materialien und Energie GmbH, Bessy II, 12489 Berlin, Germany;
Max-Planck-Institut für Chemische Physik fester Stoffe, Nöthnitzer Str. 40, 01187 Dresden, Germany;
Department of Interface Science, Fritz-Haber Institute of the Max Planck Society, 14195, Berlin, Germany;
Max Planck Institute for Chemical Energy Conversion, 45470 Mülheim, Germany;
Technical University of Freiberg, Institute of Energy Process Engineering and Chemical Engineering, Chair of Reaction Engineering, 09599 Freiberg, Germany;
Lehrstuhl für Technische Chemie I, Technische Universität München, Garching;
Fraunhofer Institute for Interfacial Engineering and Biotechnology, IGB, BioCat, Straubing branch, Straubing;
Department of Inorganic Chemistry, Fritz-Haber-Institut der Max-Planck-Gesellschaft, 14195 Berlin, Germany;
TU Dortmund University, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim/Ruhr, Germany;
Institute for a Sustainable Hydrogen Economy (INW), Forschungszentrum Jülich, 52428 Jülich, Germany;
Department of Mechanical and Process Engineering, ETH Zurich, 8092 Zurich, Switzerland;
CNRS, Physicochimie des É lectrolyteset Nanosystèmes Interfaciaux, Sorbonne Université, F-75005 Paris, France;
Institute of Catalysis Research and Technology (IKFT), Karlsruhe Institute of Technology (KIT), 76344 Eggenstein-Leopoldshafen, Germany;
Institute for Chemical Technology and Polymer Chemistry (ITCP), KIT, 76131 Karlsruhe, Germany;
Institute for Applied Materials – Electrochemical Technologies (IAM-ET), KIT, 76131 Karlsruhe, Germany;
Hydrogen Technologies, Fraunhofer Institute for Solar Energy Systems, 79110 Freiburg, Germany;
Institute for Chemical Technology and Polymer Chemistry (ITCP), Karlsruhe Institute of Technology (KIT), 76131 Karlsruhe, Germany;
Institute of Catalysis Research and Technology (IKFT), Karlsruhe Institute of Technology (KIT), 76344 Eggenstein-Leopoldshafen,
Germany;
BasCat - UniCat BASF JointLab, Technische Universität Berlin, Berlin, Germany;
Anorganische Chemie, Technische Universität Berlin, Berlin, Germany;
BASF SE, Group Research, Ludwigshafen, Germany;

Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
Max-Planck-Institut für Chemische Physik fester Stoffe, Dresden, Germany;
Max Planck Institute for Chemical Energy Conversion,
Mülheim/Germany;
RWTH Aachen University, Aachen/Germany;
TU Dortmund University, Dortmund/Germany;
C1 Green Chemicals AG, Berlin/Germany;
CreativeQuantum GmbH, Berlin/Germany;
Max-Planck-Institut für Chemische Physik fester Stoffe, Dresden, Germany;
Universität Duisburg-Essen, Essen, Germany;
Fritz-Haber-Institut der Max-Planck-Gesellschaft, Berlin, Germany;
Department of Process and Plant Technology, Brandenburg University of Technology (BTU) Cottbus-Senftenberg, Cottbus, Germany;
Chair of Biotechnology of Water Treatment, Institute of Environmental Technology, Brandenburg University of Technology (BTU) Cottbus-Senftenberg, Cottbus,Germany;
Forschungszentrum Jülich GmbH, Institute for a Sustainable Hydrogen Economy (INW), Jülich/Germany;
RWTH Aachen University, Institute of Physical Chemistry, Aachen/Germany;
ESRF – The European Synchrotron, Grenoble/France:
Deutsches Elektronen-Synchrotron (DESY), Centre for X-Ray and Nanoscience (CXNS), Hamburg/Germany;
Technical University of Munich, TUM School of Natural Sciences, Lichtenbergstr. 4, 85748 Garching near Munich;
Technical University of Munich, Catalysis Research Center, Ernst-Otto-Fischer-Straße 1, 85748 Garching near Munich, Germany;
Institut für Chemie, Technische Universität Berlin, Straße des 17. Juni 124, 10623 Berlin, Germany;
Leibniz-Institut für Katalyse e.V., Albert-Einstein-Str. 29a, 18059 Rostock, Germany;
Engler-Bunte-Institut, Karlsruher Institut für Technologie, Engler-Bunte-Ring 1, Karlsruhe 76131, Germany;
Institute of Catalysis Research and Technology, Karlsruhe Institute of Technology, 76344 Eggenstein-Leopoldshafen, Germany;
Institute for Chemical Technology and Polymer Chemistry, Karlsruhe Institute of Technology,76131 Karlsruhe, Germany;
Fritz Haber Institute of the Max Planck Society, Berlin, 14195, Germany;
Max Planck Institute for Chemical Energy Conversion, Mülheim an der Ruhr, 45470, Germany;
Clariant Produkte (Deutschland) GmbH, Heufeld, 83052, Germany;
Institute for Chemical Technology and Polymer Chemistry (ITCP), Karlsruhe Institute of Technology (KIT), Karlsruhe;
Federal University of Bahia, Salvador/Brazil;
Brandenburgische Technische Universität Cottbus-Senftenberg, Cottbus/Germany;
TUM School of Natural Sciences, Department of Chemistry, Technical University of Munich, Garching/Germany; 
ASG Analytik-Service AG, Neusäss/Germany;
Faculty of Mechanical and Process Engineering, Technical University of Applied Sciences Augsburg, Augsburg/Germany; 
Technical University of Munich, Catalysis Research Center, Garching/Germany;
Karlsruhe Institute of Technology, Eggenstein-Leopoldshafen/Germany;
University of Cape Town, Cape Town/South Africa;
Microtrac Retsch GmbH, Haan/Germany;
Karlsruhe Institute of Technology (KIT), Karlsruhe/Germany;
Max-Planck-Institut für Kohlenforschung, Mülheim an der Ruhr, Germany;
Department of Chemical Engineering, University of Bath, Claverton Down. Bath. BA2 7AY. United Kingdom;
Leibniz Institute for Catalysis, Rostock/Germany;
Institut für Nichtklassische Chemie e.V., Permoserstr. 15, 04318 Leipzig;
Melanie Iwanow, Fraunhofer-Institut für Grenzflächen- und Bioverfahrenstechnik IGB, Bio-, Elektro- und Chemokatalyse BioCat, Institutsteil Straubing, Innovationsfeld, Bioinspirierte Chemie, Schulgasse 11a, 94315 Straubing;
Laboratory of Industrial Chemistry, Department of Biochemical and Chemical Engineering, TU Dortmund University, Dortmund, Germany;
Otto von Guericke University, Magdeburg, Germany;
Max Planck Institute for Dynamics of Complex Technical Systems, Magdeburg, Germany;
Leibniz-Institut für Katalyse e.V., Rostock/Germany;
Otto von Guericke University Magdeburg, Institute of Process Engineering, Magdeburg, Germany;
Max Planck Institute for Chemical Energy Conversion, Multiphase Catalysis, Muelheim, Germany;
University Oldenburg, Oldenburg;
MAN Energy Solutions SE, Augsburg; 
TUM School of Natural Sciences and Catalysis Research Center, Garching; 
Faculty of Mechanical and Process Engineering, Technical University of Applied Sciences Augsburg, Augsburg; 
TUM School of Natural Sciences and Catalysis Research Center, Garching;
Evonik Oxeno GmbH & Co. KG, Paul-Baumann-Str. 1, 45772 Marl;
Advanced Methods for Applied Catalysis, Leibniz Institute for Catalysis e.V., 18059 Rostock;
Laboratory of Theoretical Chemistry, Ruhr University Bochum, 44801 Bochum;
Otto von Guericke University Magdeburg, Institute of Process Engineering, Magdeburg, Germany;
Max Planck Institute for Chemical Energy Conversion, Multiphase Catalysis, Muelheim, Germany;
Institute of Chemical and Electrochemical Process Engineering, Clausthal University of Technology, Clausthal-Zellerfeld, Germany;
High-Performance ComputingCenter Stuttgart (HLRS),University of Stuttgart,Stuttgart, Germany;
Anhalt University of Applied Sciences, Koethen, Germany; 
Otto von Guericke University, Magdeburg, Germany;
Fraunhofer Institute for Microengineering and Microsystems IMM, Carl-Zeiss-Str. 18-20, 55129 Mainz, Germany
Karlsruhe Institute of Technology (KIT), Karlsruhe/Germany;
Institute of Process Engineering at Otto von Guericke University Magdeburg/Germany; 
Institute of Chemistry at Otto von Guericke University Magdeburg/Germany;
Anhalt University of Applied Sciences, Process Engineering Koethen/Germany;
University of Greifswald, Institute of Biochemistry;
Otto-von-Guericke University Magdeburg, Institute of Chemistry; 
Anhalt University of Applied Sciences, Applied Biosciences and Process Engineering; 
Otto-von-Guericke University Magdeburg, Institute of Process Engineering; 
University of Greifswald, Institute of Biochemistry;
High-Performance Computing Center Stuttgart(HLRS),University of Stuttgart,Stuttgart, Germany;
Leibniz-Institut für Katalyse, Albert-Einstein-Str. 29A, 18059 Rostock, Germany;
High Performance Computing Center Stuttgart (HLRS), Stuttgart, Germany;
Karlsruhe Institute of Technology, Karlsruhe/Germany;
Leibniz Institute für Catalysis, Rostock/Germany;
University of Rostock, Rostock/Germany;
Helmholtz-Zentrum Berlin, Berlin / Germany;
University of Stuttgart, Stuttgart / Germany;
Chair of Inorganic Chemistry with Focus on Novel Materials, Technical University of Munich, Lichtenbergstraße 4, 85748 Garching;
High-Performance Computing Center Stuttgart (HLRS), University of Stuttgart, Stuttgart, Germany;
Fraunhofer FOKUS, TU Berlin, Berlin, Germany;
Institute of Energy Technologies, Fundamental Electrochemistry (IET-1), Forschungszentrum Jülich GmbH, Germany;
Electrochemical Reaction Engineering, RWTH Aachen University, Germany;
Institute of Physical Chemistry, RWTH Aachen University, 52074 Aachen, Germany;
"""


# print("--- Affiliation 1 ---")
# parsed_affil_1 = parse_affiliation_with_ollama(raw_affiliation_1)
# print(json.dumps(parsed_affil_1, indent=2))

# print("\n--- Affiliation 2 ---")
# parsed_affil_2 = parse_affiliation_with_ollama(raw_affiliation_2)
# print(json.dumps(parsed_affil_2, indent=2))

print("\n--- Affiliation 3 ---")
parsed_affil_3 = parse_affiliation_with_ollama(raw_affiliation_3)
print(json.dumps(parsed_affil_3, indent=2))